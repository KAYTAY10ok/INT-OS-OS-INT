/* Test-image-only TCP server/client. No DNS, subprocesses, or remote discovery. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

static const char token[] = "INT_NET_PROBE_OK\n";

static int64_t now_ms(void)
{
    struct timespec time;
    if (clock_gettime(CLOCK_MONOTONIC, &time) != 0) {
        perror("clock_gettime");
        exit(1);
    }
    return (int64_t)time.tv_sec * 1000 + time.tv_nsec / 1000000;
}

static unsigned number(const char *text, unsigned minimum, unsigned maximum)
{
    char *end;
    unsigned long value;
    errno = 0;
    value = strtoul(text, &end, 10);
    if (errno || !*text || *end || value < minimum || value > maximum) {
        fprintf(stderr, "invalid numeric argument: %s\n", text);
        exit(1);
    }
    return (unsigned)value;
}

/* 0=ready, 1=error, 2=deadline. POLLERR is read through SO_ERROR/recv. */
static int wait_ready(int fd, short events, int64_t deadline)
{
    struct pollfd descriptor = { .fd = fd, .events = events };
    for (;;) {
        int64_t remaining = deadline - now_ms();
        int result;
        if (remaining <= 0) return 2;
        result = poll(&descriptor, 1, remaining > INT_MAX ? INT_MAX : (int)remaining);
        if (result < 0 && errno == EINTR) continue;
        if (result < 0 || descriptor.revents & POLLNVAL) return 1;
        if (result == 0) return 2;
        if (descriptor.revents & (events | POLLERR | POLLHUP)) return 0;
    }
}

static struct sockaddr_in endpoint(const char *address, unsigned port)
{
    struct sockaddr_in result = { .sin_family = AF_INET, .sin_port = htons(port) };
    if (inet_pton(AF_INET, address, &result.sin_addr) != 1) {
        fprintf(stderr, "an IPv4 literal is required: %s\n", address);
        exit(1);
    }
    return result;
}

static int client(const char *address, unsigned port, unsigned timeout, unsigned local_port)
{
    struct sockaddr_in target = endpoint(address, port);
    struct sockaddr_in local = endpoint("0.0.0.0", local_port);
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    int result = 1;
    int error = 0;
    socklen_t length = sizeof(error);
    int64_t deadline = now_ms() + timeout;
    char reply[sizeof(token) - 1];
    size_t used = 0;
    if (fd < 0) { perror("socket"); return 1; }
    if (bind(fd, (struct sockaddr *)&local, sizeof(local)) != 0) { perror("bind"); goto done; }
    if (connect(fd, (struct sockaddr *)&target, sizeof(target)) != 0) {
        if (errno != EINPROGRESS) { perror("connect"); goto done; }
        result = wait_ready(fd, POLLOUT, deadline);
        if (result) goto done;
        if (getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &length) || error) {
            fprintf(stderr, "connect: %s\n", strerror(error ? error : errno));
            result = 1;
            goto done;
        }
    }
    while (used < sizeof(reply)) {
        ssize_t received;
        result = wait_ready(fd, POLLIN, deadline);
        if (result) goto done;
        received = recv(fd, reply + used, sizeof(reply) - used, 0);
        if (received < 0 && (errno == EAGAIN || errno == EINTR)) continue;
        if (received <= 0) { fprintf(stderr, "server closed without the complete test token\n"); result = 1; goto done; }
        used += (size_t)received;
    }
    result = memcmp(reply, token, sizeof(reply)) ? 1 : 0;
    if (result) fprintf(stderr, "incorrect test token\n");
done:
    if (result == 2) fprintf(stderr, "connection/token deadline expired\n");
    close(fd);
    return result;
}

static int server(const char *address, unsigned port, const char *ready, unsigned timeout)
{
    struct sockaddr_in local = endpoint(address, port);
    socklen_t length = sizeof(local);
    int one = 1, fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    int result = 1, ready_fd;
    int64_t deadline = now_ms() + timeout;
    char line[16];
    int line_length;
    if (fd < 0) { perror("socket"); return 1; }
    if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one)) ||
        bind(fd, (struct sockaddr *)&local, sizeof(local)) || listen(fd, 4) ||
        getsockname(fd, (struct sockaddr *)&local, &length)) {
        perror("server setup"); goto done;
    }
    ready_fd = open(ready, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (ready_fd < 0) { perror("ready file"); goto done; }
    line_length = snprintf(line, sizeof(line), "%u\n", ntohs(local.sin_port));
    if (write(ready_fd, line, (size_t)line_length) != line_length) {
        perror("ready write"); close(ready_fd); goto done;
    }
    if (close(ready_fd)) { perror("ready close"); goto done; }
    for (;;) {
        int connection;
        size_t sent = 0;
        int status = wait_ready(fd, POLLIN, deadline);
        if (status == 2) { result = 0; break; }
        if (status) break;
        connection = accept4(fd, NULL, NULL, SOCK_CLOEXEC | SOCK_NONBLOCK);
        if (connection < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (connection < 0) { perror("accept"); break; }
        while (sent < sizeof(token) - 1) {
            ssize_t written;
            if (wait_ready(connection, POLLOUT, deadline)) break;
            written = send(connection, token + sent, sizeof(token) - 1 - sent, MSG_NOSIGNAL);
            if (written < 0 && (errno == EINTR || errno == EAGAIN)) continue;
            if (written <= 0) break;
            sent += (size_t)written;
        }
        close(connection);
    }
done:
    close(fd);
    return result;
}

int main(int argc, char **argv)
{
    if ((argc == 5 || argc == 6) && !strcmp(argv[1], "client"))
        return client(argv[2], number(argv[3], 1, 65535), number(argv[4], 1, 300000),
                      argc == 6 ? number(argv[5], 0, 65535) : 0);
    if (argc == 6 && !strcmp(argv[1], "server"))
        return server(argv[2], number(argv[3], 0, 65535), argv[4], number(argv[5], 1, 300000));
    fprintf(stderr, "usage: %s client IPv4 PORT TIMEOUT_MS [SOURCE_PORT]\n"
                    "       %s server IPv4 PORT READYFILE DEADLINE_MS\n", argv[0], argv[0]);
    return 1;
}
