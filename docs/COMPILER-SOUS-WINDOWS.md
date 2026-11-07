# Compiler INT Linux sur un PC Windows (WSL2)

WSL2 fait tourner un vrai Linux (Ubuntu) à l'intérieur de Windows. Windows
n'est pas modifié en dehors de ce disque virtuel Linux, que tu peux
supprimer à tout moment. Une compilation complète d'INT Linux (image
console, bureau, ISO) prend **plusieurs heures la première fois**, puis
beaucoup moins grâce aux caches.

## Ce qu'il faut

- Windows 11 (ou Windows 10 22H2 à jour).
- Virtualisation activée dans le BIOS/UEFI (Intel VT-x ou AMD-V/SVM). Le
  Gestionnaire des tâches → Performances → Processeur affiche
  « Virtualisation : Activé ».
- **150 à 200 Go libres**, idéalement sur un SSD.
- 16 Go de RAM conseillés (8 Go possibles, en plus lent).

## 1. Installer WSL2 et Ubuntu

Ouvre **PowerShell en administrateur** et lance :

```powershell
wsl --install -d Ubuntu-24.04
```

Redémarre si Windows le demande. Au premier lancement d'Ubuntu, choisis un
nom d'utilisateur et un mot de passe Linux (ils ne servent qu'à Ubuntu).

Si ton disque `C:` manque de place, déplace Ubuntu sur un autre disque
(exemple `D:`), depuis PowerShell :

```powershell
wsl --shutdown
wsl --manage Ubuntu-24.04 --move D:\WSL\Ubuntu
```

## 2. Donner assez de mémoire à WSL

Crée le fichier `%UserProfile%\.wslconfig` (par exemple
`C:\Users\TonNom\.wslconfig`) avec, pour un PC à 16 Go :

```ini
[wsl2]
memory=12GB
processors=4
swap=8GB
```

Puis dans PowerShell : `wsl --shutdown`, et rouvre Ubuntu.

## 3. Préparer Ubuntu

Dans le terminal Ubuntu :

```bash
sudo apt update
```

```bash
sudo apt install -y git docker.io qemu-system-x86 python3
```

```bash
sudo usermod -aG docker "$USER"
```

Active systemd pour que Docker démarre tout seul : édite
`/etc/wsl.conf` (`sudo nano /etc/wsl.conf`) et mets :

```ini
[boot]
systemd=true
```

Puis dans PowerShell : `wsl --shutdown`, rouvre Ubuntu et vérifie :

```bash
docker run --rm hello-world
```

## 4. Récupérer le projet

Travaille **dans le système de fichiers Linux** (`~`), pas dans `/mnt/c` :
c'est beaucoup plus rapide et évite les problèmes de majuscules.

```bash
cd ~
```

```bash
git clone https://github.com/KAYTAY10ok/INT-OS-OS-INT.git
```

Le dépôt est privé : Git te demandera ton nom GitHub et un jeton d'accès
(GitHub → Settings → Developer settings → Personal access tokens), à
taper uniquement dans ton terminal. Ne le colle jamais dans une
conversation.

## 5. Compiler

```bash
cd ~/INT-OS-OS-INT
```

```bash
./scripts/int bootstrap
```

```bash
./scripts/int builder
```

```bash
./scripts/int --profile desktop configure
```

```bash
./scripts/int --profile desktop build int-image-desktop
```

Les sources, caches et images vont dans `~/int-linux-work`. Une seule
compilation à la fois.

## 6. Essayer

```bash
./scripts/int --profile desktop run
```

Sous Windows 11, la fenêtre QEMU s'ouvre directement (WSLg). Voir
[ESSAYER.md](../ESSAYER.md) pour la suite.

## Laisser Claude travailler sur ton PC

Une session Claude dans le cloud ne peut pas atteindre ton PC toute seule,
et **tu n'as pas à lui donner de clé** (ne colle jamais de clé ou de mot de
passe dans une conversation). Pour que Claude compile sur ton PC :

- installe l'application **Claude Desktop** sur Windows et ouvre une session
  Claude Code dans le dossier du projet ; ou
- dans le terminal Ubuntu (WSL), dans `~/INT-OS-OS-INT`, lance
  `claude remote-control` (après avoir installé Claude Code) : la session
  apparaît alors dans l'application Claude et peut travailler sur ce
  dossier, avec ton accord à chaque étape sensible.
