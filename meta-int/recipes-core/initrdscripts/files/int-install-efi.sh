#!/bin/sh
# INT Linux disk installer (UEFI), French/English.
#
# Called by the live initramfs for the "install" boot entry as:
#   install-efi.sh MEDIA_DIR ROOTFS_IMAGE
# It erases ONE whole disk chosen by number, after a double confirmation.
# All prompts use digits only, so they work on any keyboard layout before a
# keymap is loaded (AZERTY/QWERTZ digit keys send the same codes).
#
# Test hooks (never set on a real system):
#   INT_INSTALL_DRY_RUN=1  print the commands instead of running them
#   INT_SYS=DIR            read block devices from DIR/block instead of /sys
#   INT_MEDIA_ROOT=DIR     where the live media is mounted (default /run/media)
#   INT_MEMINFO=FILE       memory information file (default /proc/meminfo)
#   INT_MOUNTS=FILE        mount table (default /proc/mounts)

PATH=/sbin:/bin:/usr/sbin:/usr/bin

MEDIA="${1%/}"
ROOTFS_IMAGE="$2"
SYS="${INT_SYS:-/sys}"
MEDIA_ROOT="${INT_MEDIA_ROOT:-/run/media}"
MEMINFO="${INT_MEMINFO:-/proc/meminfo}"
DRY_RUN="${INT_INSTALL_DRY_RUN:-0}"
LANG_CODE=en

# --- messages ---------------------------------------------------------------

msg() {
	if [ "$LANG_CODE" = fr ]; then
		case "$1" in
		title) echo "=== Installation d'INT Linux ===" ;;
		keyboard) echo "Disposition du clavier :" ;;
		edition) echo "Edition :" ;;
		ed_intos) echo "INT-OS  - minimaliste, leger" ;;
		ed_osint) echo "OS-INT  - cyber/opsec, complet" ;;
		encrypt) echo "Chiffrer le disque (LUKS2) ? Il faudra une phrase secrete a chaque demarrage." ;;
		enc_yes) echo "Oui, chiffrer (recommande pour OS-INT ; pas de swap en clair)" ;;
		enc_no) echo "Non" ;;
		passinfo) echo "Choisis la phrase secrete du disque (deux fois). Elle sera demandee au demarrage avec les MEMES touches qu'ici. Si elle est perdue, les donnees sont perdues." ;;
		passretry) echo "Phrase secrete refusee ou differente, recommence." ;;
		pass1) printf "Phrase secrete (invisible) : " ;;
		pass2) printf "Retape-la pour verifier : " ;;
		passshort) echo "Trop courte : au moins 8 caracteres." ;;
		ai) echo "IA locale (super commande du systeme, fonctionne hors ligne) :" ;;
		ai_none) echo "Aucune" ;;
		ai_small) echo "Petite - Qwen2.5 1.5B (4 Go de RAM ou plus, ~1 Go a telecharger)" ;;
		ai_large) echo "Grande - Qwen2.5 7B (16 Go de RAM ou plus, ~5 Go a telecharger)" ;;
		ai_note) echo "Le modele sera telecharge au premier demarrage avec Internet." ;;
		disks) echo "Disques disponibles (le disque choisi sera ENTIEREMENT efface) :" ;;
		nodisk) echo "Aucun disque d'installation trouve (en dehors de la cle live). Installation annulee." ;;
		choose) echo "Tape le numero puis Entree (0 = annuler) :" ;;
		invalid) echo "Choix invalide, recommence." ;;
		warn) echo "ATTENTION : TOUTES les donnees de ce disque vont etre DEFINITIVEMENT effacees :" ;;
		confirm) echo "Pour confirmer, retape le numero de ce disque (0 = annuler) :" ;;
		cancel) echo "Installation annulee. Aucun disque n'a ete modifie." ;;
		parts) echo "Partitions prevues :" ;;
		working) echo "Installation en cours, ne pas eteindre..." ;;
		copying) echo "Copie du systeme..." ;;
		bootentry) echo "Ajout de l'entree de demarrage \"INT Linux\" dans le firmware..." ;;
		bootwarn) echo "Entree firmware non creee : choisis le disque dans le menu de demarrage du PC si besoin." ;;
		done) echo "Installation reussie. Retire la cle USB puis appuie sur Entree pour redemarrer." ;;
		dryrun) echo "[simulation] aucune commande n'est executee" ;;
		failed) echo "ECHEC de l'installation a l'etape :" ;;
		esac
	elif [ "$LANG_CODE" = both ]; then
		case "$1" in
		choose) echo "Numero puis Entree / Number, then Enter (0 = annuler/cancel) :" ;;
		invalid) echo "Choix invalide / Invalid choice." ;;
		cancel) echo "Installation annulee / cancelled." ;;
		esac
	else
		case "$1" in
		title) echo "=== INT Linux installation ===" ;;
		keyboard) echo "Keyboard layout:" ;;
		edition) echo "Edition:" ;;
		ed_intos) echo "INT-OS  - minimal, lightweight" ;;
		ed_osint) echo "OS-INT  - cyber/opsec, complete" ;;
		encrypt) echo "Encrypt the disk (LUKS2)? A passphrase will be needed at every boot." ;;
		enc_yes) echo "Yes, encrypt (recommended for OS-INT; no plain swap)" ;;
		enc_no) echo "No" ;;
		passinfo) echo "Choose the disk passphrase (twice). It is asked at boot with the SAME keys as here. If it is lost, the data is lost." ;;
		passretry) echo "Passphrase rejected or different, try again." ;;
		pass1) printf "Passphrase (hidden): " ;;
		pass2) printf "Type it again to verify: " ;;
		passshort) echo "Too short: at least 8 characters." ;;
		ai) echo "Local AI (system super command, works offline):" ;;
		ai_none) echo "None" ;;
		ai_small) echo "Small - Qwen2.5 1.5B (4 GB RAM or more, ~1 GB download)" ;;
		ai_large) echo "Large - Qwen2.5 7B (16 GB RAM or more, ~5 GB download)" ;;
		ai_note) echo "The model is downloaded at first boot when online." ;;
		disks) echo "Available disks (the chosen disk will be COMPLETELY erased):" ;;
		nodisk) echo "No installation disk found (besides the live stick). Installation aborted." ;;
		choose) echo "Type the number, then Enter (0 = cancel):" ;;
		invalid) echo "Invalid choice, try again." ;;
		warn) echo "WARNING: ALL data on this disk will be PERMANENTLY erased:" ;;
		confirm) echo "To confirm, type this disk's number again (0 = cancel):" ;;
		cancel) echo "Installation cancelled. No disk was modified." ;;
		parts) echo "Planned partitions:" ;;
		working) echo "Installing, do not power off..." ;;
		copying) echo "Copying the system..." ;;
		bootentry) echo "Adding the \"INT Linux\" firmware boot entry..." ;;
		bootwarn) echo "Firmware entry not created: pick the disk in the PC boot menu if needed." ;;
		done) echo "Installation successful. Remove the USB stick, then press Enter to reboot." ;;
		dryrun) echo "[dry run] no command is executed" ;;
		failed) echo "Installation FAILED at step:" ;;
		esac
	fi
}

# --- helpers ----------------------------------------------------------------

run() {
	if [ "$DRY_RUN" = 1 ]; then
		echo "RUN: $*"
	else
		"$@" || fail "$*"
	fi
}

fail() {
	msg failed
	echo "  $1"
	exit 1
}

# ask N: read a number between 0 and N, repeating until valid.
ask() {
	while :; do
		msg choose
		IFS= read -r answer || { msg cancel; exit 1; }
		case "$answer" in
		''|*[!0-9]*) msg invalid ;;
		*)
			if [ "$answer" -ge 0 ] && [ "$answer" -le "$1" ]; then
				return 0
			fi
			msg invalid
			;;
		esac
	done
}

# Strip a partition suffix from the live device name to get its disk.
live_disk() {
	dev=$(awk -v m="$MEDIA_ROOT/$MEDIA" '$2 == m {print $1; exit}' "${INT_MOUNTS:-/proc/mounts}" 2>/dev/null)
	dev=${dev#/dev/}
	case "$dev" in
	nvme*|mmcblk*) echo "${dev%p[0-9]*}" ;;
	*) echo "${dev%%[0-9]*}" ;;
	esac
}

list_disks() {
	live=$(live_disk)
	for path in "$SYS"/block/*; do
		name=${path##*/}
		case "$name" in
		loop*|ram*|sr*|zram*|dm-*|md*|mmcblk*boot*|mmcblk*rpmb) continue ;;
		esac
		[ -n "$live" ] && [ "$name" = "$live" ] && continue
		echo "$name"
	done
}

disk_info() {
	sectors=$(cat "$SYS/block/$1/size" 2>/dev/null || echo 0)
	gb=$((sectors / 2097152))
	model=$(cat "$SYS/block/$1/device/model" 2>/dev/null | sed 's/  *$//')
	echo "/dev/$1  ${gb} GiB  ${model:-?}"
}

# --- questions --------------------------------------------------------------

echo "=== INT Linux ==="
echo "Langue / Language :"
echo "1) Francais"
echo "2) English"
LANG_CODE=both
ask 2
case "$answer" in 0) msg cancel; exit 1 ;; 1) LANG_CODE=fr ;; 2) LANG_CODE=en ;; esac
[ "$DRY_RUN" = 1 ] && msg dryrun
msg title

msg keyboard
echo "1) Suisse romand / Swiss French (fr_CH)"
echo "2) Francais / French AZERTY (fr)"
echo "3) Suisse alemanique / Swiss German (de_CH)"
echo "4) US English (us)"
echo "5) Belge / Belgian (be)"
ask 5
case "$answer" in
0) msg cancel; exit 1 ;;
1) KEYMAP=fr_CH; XKB_LAYOUT=ch; XKB_VARIANT=fr ;;
2) KEYMAP=fr; XKB_LAYOUT=fr; XKB_VARIANT= ;;
3) KEYMAP=de_CH; XKB_LAYOUT=ch; XKB_VARIANT= ;;
4) KEYMAP=us; XKB_LAYOUT=us; XKB_VARIANT= ;;
5) KEYMAP=be-latin1; XKB_LAYOUT=be; XKB_VARIANT= ;;
esac

msg edition
echo "1) $(msg ed_intos)"
echo "2) $(msg ed_osint)"
ask 2
case "$answer" in 0) msg cancel; exit 1 ;; 1) EDITION=int-os ;; 2) EDITION=os-int ;; esac

msg encrypt
echo "1) $(msg enc_yes)"
echo "2) $(msg enc_no)"
ask 2
case "$answer" in 0) msg cancel; exit 1 ;; 1) ENCRYPT=1 ;; 2) ENCRYPT=0 ;; esac

# Local AI model size. The research-licensed 3B model is not offered here.
mem_kb_ai=$(awk '/^MemTotal:/ {print $2}' "$MEMINFO" 2>/dev/null)
msg ai
echo "1) $(msg ai_none)"
echo "2) $(msg ai_small)"
echo "3) $(msg ai_large)"
ask 3
case "$answer" in 0) msg cancel; exit 1 ;; 1) AI_MODEL=none ;; 2) AI_MODEL=1.5b ;; 3) AI_MODEL=7b ;; esac
if [ "$AI_MODEL" != none ]; then
	msg ai_note
	[ "${mem_kb_ai:-0}" -lt 3500000 ] && [ "$AI_MODEL" = 1.5b ] && echo "!! RAM < 4 GB"
	[ "${mem_kb_ai:-0}" -lt 14000000 ] && [ "$AI_MODEL" = 7b ] && echo "!! RAM < 16 GB"
fi

DISKS=$(list_disks)
if [ -z "$DISKS" ]; then
	msg nodisk
	exit 1
fi
msg disks
count=0
for d in $DISKS; do
	count=$((count + 1))
	echo "$count) $(disk_info "$d")"
done
ask "$count"
[ "$answer" = 0 ] && { msg cancel; exit 1; }
choice=$answer
TARGET=$(echo "$DISKS" | sed -n "${choice}p")

msg warn
echo "  $(disk_info "$TARGET")"
msg confirm
IFS= read -r again || { msg cancel; exit 1; }
if [ "$again" != "$choice" ]; then
	msg cancel
	exit 1
fi

# read_secret: read one line without echo into $secret (the console in the
# initramfs is not a controlling terminal, so cryptsetup would echo it).
read_secret() {
	stty -echo 2>/dev/null
	IFS= read -r secret || secret=""
	stty echo 2>/dev/null
	echo
}

# ask_passphrase: hidden entry, typed twice, compared; result in $PASSPHRASE.
ask_passphrase() {
	while :; do
		msg pass1; read_secret; first=$secret
		msg pass2; read_secret; second=$secret
		if [ "${#first}" -lt 8 ]; then
			msg passshort
		elif [ "$first" != "$second" ]; then
			msg passretry
		else
			PASSPHRASE=$first
			first=""; second=""; secret=""
			return 0
		fi
	done
}

# --- layout -----------------------------------------------------------------

device=/dev/$TARGET
part_prefix=""
case "$TARGET" in nvme*|mmcblk*) part_prefix=p ;; esac
bootfs=${device}${part_prefix}1
rootfs=${device}${part_prefix}2
swap=${device}${part_prefix}3

sectors=$(cat "$SYS/block/$TARGET/size" 2>/dev/null || echo 0)
disk_mb=$((sectors / 2048))
mem_kb=$(awk '/^MemTotal:/ {print $2}' "$MEMINFO" 2>/dev/null)
swap_mb=$(( ${mem_kb:-1048576} / 1024 ))
[ "$swap_mb" -gt 4096 ] && swap_mb=4096
[ "$swap_mb" -lt 512 ] && swap_mb=512
boot_mb=512
root_end_mb=$((disk_mb - swap_mb))
# An unencrypted swap would leak memory contents of an encrypted system.
[ "$ENCRYPT" = 1 ] && { swap_mb=0; root_end_mb=$disk_mb; }
if [ "$root_end_mb" -le $((boot_mb + 4096)) ]; then
	fail "disk too small (${disk_mb} MiB)"
fi

msg parts
echo "  ${bootfs}  EFI     ${boot_mb} MiB"
if [ "$ENCRYPT" = 1 ]; then
	echo "  ${rootfs}  LUKS2 + ext4    $((root_end_mb - boot_mb)) MiB"
else
	echo "  ${rootfs}  ext4    $((root_end_mb - boot_mb)) MiB"
	echo "  ${swap}  swap    ${swap_mb} MiB"
fi
msg working

# --- install ----------------------------------------------------------------

if [ "$DRY_RUN" != 1 ]; then
	# The live automounter must not grab the new partitions.
	rm -f /etc/udev/rules.d/automount.rules /etc/udev/scripts/mount* 2>/dev/null
	umount ${device}* 2>/dev/null
	mkdir -p /tmp
	[ -e /etc/mtab ] || ln -sf /proc/mounts /etc/mtab
fi

run dd if=/dev/zero of="$device" bs=1M count=4
run parted -s "$device" mklabel gpt
run parted -s "$device" mkpart ESP fat32 1MiB "${boot_mb}MiB"
run parted -s "$device" set 1 esp on
if [ "$ENCRYPT" = 1 ]; then
	run parted -s "$device" mkpart root ext4 "${boot_mb}MiB" 100%
else
	run parted -s "$device" mkpart root ext4 "${boot_mb}MiB" "${root_end_mb}MiB"
	run parted -s "$device" mkpart swap linux-swap "${root_end_mb}MiB" 100%
fi

if [ "$DRY_RUN" != 1 ]; then
	C=0
	while [ $C -lt 10 ] && { [ ! -e "$bootfs" ] || [ ! -e "$rootfs" ] || { [ "$ENCRYPT" != 1 ] && [ ! -e "$swap" ]; }; }; do
		C=$((C + 1)); sleep 1
	done
fi

run mkfs.vfat -F 32 -n INT-EFI "$bootfs"
rootdev=$rootfs
if [ "$ENCRYPT" = 1 ]; then
	msg passinfo
	ask_passphrase
	if [ "$DRY_RUN" = 1 ]; then
		echo "RUN: cryptsetup luksFormat --type luks2 --pbkdf argon2id --key-file=- $rootfs (passphrase on stdin)"
		echo "RUN: cryptsetup open --type luks2 --key-file=- $rootfs introot (passphrase on stdin)"
	else
		# The passphrase goes to cryptsetup only through a pipe from the shell
		# builtin printf: never in arguments, environment, files or logs.
		printf '%s' "$PASSPHRASE" | cryptsetup -q luksFormat --type luks2 --pbkdf argon2id \
			--label INT-CRYPT --key-file=- "$rootfs" || fail "cryptsetup luksFormat"
		printf '%s' "$PASSPHRASE" | cryptsetup open --type luks2 --key-file=- "$rootfs" introot \
			|| fail "cryptsetup open"
	fi
	PASSPHRASE=""
	rootdev=/dev/mapper/introot
fi
run mkfs.ext4 -F -q -L INT-ROOT "$rootdev"
[ "$ENCRYPT" = 1 ] || run mkswap -L INT-SWAP "$swap"

run mkdir -p /tgt_root /src_root /tgt_boot
run mount "$rootdev" /tgt_root
run mount -o ro,loop "$MEDIA_ROOT/$MEDIA/$ROOTFS_IMAGE" /src_root
msg copying
run cp -a /src_root/. /tgt_root/
run umount /src_root

if [ "$DRY_RUN" = 1 ]; then
	boot_uuid=DRYRUN-BOOT; swap_puuid=DRYRUN-SWAP; root_puuid=DRYRUN-ROOT
else
	boot_uuid=$(blkid -o value -s UUID "$bootfs")
	[ "$ENCRYPT" = 1 ] || swap_puuid=$(blkid -o value -s PARTUUID "$swap")
	root_puuid=$(blkid -o value -s PARTUUID "$rootfs")
fi

write() {
	# write FILE: append stdin to FILE (or show it in a dry run)
	if [ "$DRY_RUN" = 1 ]; then
		echo "WRITE: $1"; sed 's/^/  | /'
	else
		cat >> "$1" || fail "write $1"
	fi
}

if [ "$ENCRYPT" = 1 ]; then
	write /tgt_root/etc/fstab <<EOF
UUID=$boot_uuid  /boot  vfat  umask=0077  0  2
EOF
else
	write /tgt_root/etc/fstab <<EOF
PARTUUID=$swap_puuid  none   swap  defaults  0  0
UUID=$boot_uuid  /boot  vfat  umask=0077  0  2
EOF
fi
[ "$DRY_RUN" = 1 ] || mkdir -p /tgt_root/etc/int
[ "$DRY_RUN" = 1 ] || : > /tgt_root/etc/int/install.conf
write /tgt_root/etc/int/install.conf <<EOF
# Written by the INT installer. Read by first-boot and desktop setup.
INT_EDITION=$EDITION
INT_LANGUAGE=$LANG_CODE
INT_KEYMAP=$KEYMAP
INT_XKB_LAYOUT=$XKB_LAYOUT
INT_XKB_VARIANT=$XKB_VARIANT
INT_ENCRYPTED=$ENCRYPT
INT_AI_MODEL=$AI_MODEL
EOF
[ "$DRY_RUN" = 1 ] || : > /tgt_root/etc/vconsole.conf
write /tgt_root/etc/vconsole.conf <<EOF
KEYMAP=$KEYMAP
EOF
if [ "$LANG_CODE" = fr ]; then locale=fr_FR.UTF-8; else locale=en_US.UTF-8; fi
[ "$DRY_RUN" = 1 ] || : > /tgt_root/etc/locale.conf
write /tgt_root/etc/locale.conf <<EOF
LANG=$locale
EOF
[ "$DRY_RUN" = 1 ] || : > /tgt_root/etc/hostname
echo "$EDITION" | write /tgt_root/etc/hostname
if [ "$EDITION" = os-int ]; then
	# OS-INT: a new random MAC address for Ethernet and Wi-Fi at each boot.
	[ "$DRY_RUN" = 1 ] || { mkdir -p /tgt_root/etc/systemd/network; : > /tgt_root/etc/systemd/network/10-int-mac-random.link; }
	write /tgt_root/etc/systemd/network/10-int-mac-random.link <<EOF
[Match]
Type=ether wlan

[Link]
MACAddressPolicy=random
NamePolicy=kernel database onboard slot path
EOF
fi
if [ "$ENCRYPT" = 1 ]; then
	run cp /tgt_root/usr/lib/int/initrd-luks.cpio.gz /tmp/initrd-luks.cpio.gz
fi
run umount /tgt_root
if [ "$ENCRYPT" = 1 ]; then
	run cryptsetup close introot
fi

run mount "$bootfs" /tgt_boot
run mkdir -p /tgt_boot/EFI/BOOT
run cp "$MEDIA_ROOT/$MEDIA/EFI/BOOT/bootx64.efi" /tgt_boot/EFI/BOOT/BOOTX64.EFI
for kernel in bzImage; do
	run cp "$MEDIA_ROOT/$MEDIA/$kernel" /tgt_boot/
done
[ "$DRY_RUN" = 1 ] || : > /tgt_boot/EFI/BOOT/grub.cfg
if [ "$ENCRYPT" = 1 ]; then
	run cp /tmp/initrd-luks.cpio.gz /tgt_boot/initrd-luks.cpio.gz
	write /tgt_boot/EFI/BOOT/grub.cfg <<EOF
default=0
timeout=3
menuentry 'INT Linux' {
linux /bzImage intluks=PARTUUID=$root_puuid root=/dev/mapper/introot rw rootwait quiet loglevel=3
initrd /initrd-luks.cpio.gz
}
EOF
else
	write /tgt_boot/EFI/BOOT/grub.cfg <<EOF
default=0
timeout=3
menuentry 'INT Linux' {
linux /bzImage root=PARTUUID=$root_puuid rw rootwait quiet loglevel=3
}
EOF
fi
run umount /tgt_boot

msg bootentry
if [ "$DRY_RUN" = 1 ]; then
	echo "RUN: efibootmgr -c -d $device -p 1 -L INT Linux -l \\EFI\\BOOT\\BOOTX64.EFI"
else
	if [ -d /sys/firmware/efi ] && ! grep -q " efivarfs " /proc/mounts; then
		mount -t efivarfs efivarfs /sys/firmware/efi/efivars || echo "efivarfs: mount failed"
	fi
	# Show the firmware's answer: a silent failure would leave the PC unbootable
	# on firmwares that do not fall back to the removable path.
	if efibootmgr -c -d "$device" -p 1 -L "INT Linux" -l '\EFI\BOOT\BOOTX64.EFI' 2>&1 | tail -n 4 \
			&& efibootmgr 2>/dev/null | grep -q "INT Linux"; then
		:
	else
		msg bootwarn
	fi
fi

[ "$DRY_RUN" = 1 ] || sync
msg done
[ "$DRY_RUN" = 1 ] && exit 0
read -r enter
reboot -f
