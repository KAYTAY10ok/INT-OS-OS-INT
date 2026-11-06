# Essayer INT Linux (version de développement)

Ce guide sert à **utiliser** INT Linux à la main dans une machine virtuelle
QEMU. Ce n'est ni une version publiée ni un système installable sur un vrai
PC. Les validations automatiques et leurs limites sont décrites dans
`ROADMAP.md`, `BUILDING.md` et `docs/development/validation-*.md`.

## Ce que tu peux tester aujourd'hui

| Image | Contenu | Validation automatique existante |
| --- | --- | --- |
| `int-image-core` | Console : création du premier propriétaire, connexion, `sudo` avec mot de passe, root verrouillé, pare-feu nftables, réseau DHCP | Oui, en QEMU (`core-check`), sur l'image de test équivalente |
| `int-image-desktop` | La console ci-dessus + bureau Sway INT (terminal foot, lanceur fuzzel, barre d'état) | Oui pour les images de test du bureau (`desktop-check`, `graphics-check`) |

Pas encore testable : installation sur disque, mises à jour par paquets
signés, matériel physique, son, suspension, Wi-Fi.

## Sous Windows

`scripts/int` cible Linux. Sous Windows, utilise le paquet prêt à l'emploi
`INT-Linux-bureau.zip` (noyau, image du bureau, `lancer-INT-Linux.bat`,
`reinitialiser.bat`, `LISEZMOI.txt`) : installe QEMU pour Windows
(https://qemu.weilnetz.de/w64/), dézippe, puis double-clique sur
`lancer-INT-Linux.bat`. Il utilise l'accélération Windows Hypervisor
Platform si elle est activée, sinon l'émulation (plus lente), et travaille
sur une copie de l'image. Ce paquet n'est pas versionné dans Git (environ
87 Mo) ; il a été transmis directement au propriétaire le 2026-11-06.
La ligne de commande QEMU du `.bat` a été vérifiée sous Linux (démarrage
du noyau et montage du système de fichiers) ; elle n'a pas été exécutée
sous Windows.

## Prérequis

- Linux x86-64 avec `qemu-system-x86_64` (Debian/Ubuntu :
  `sudo apt install qemu-system-x86`). L'accès à `/dev/kvm` rend la VM
  beaucoup plus rapide ; sans lui, elle fonctionne mais lentement.
- Les images déjà construites dans `../int-linux-work` (ou `INT_WORKDIR`).
  Si elles n'existent pas encore :

```sh
./scripts/int build int-image-core
./scripts/int --profile desktop build int-image-desktop
```

## Lancer la console

```sh
./scripts/int run
```

La console série s'affiche dans ton terminal. Au premier démarrage, crée le
compte propriétaire (nom et mot de passe), puis connecte-toi. Pour quitter
QEMU : `Ctrl-A` puis `X`. Le compte et tes fichiers sont conservés entre deux
lancements ; `./scripts/int run --reset` repart de l'image construite.

## Lancer le bureau

```sh
./scripts/int --profile desktop run
```

Une fenêtre QEMU s'ouvre. Crée le compte propriétaire dans cette fenêtre,
connecte-toi, puis lance :

```sh
start-int-desktop
```

Raccourcis (`$mod` = touche Super/Windows) : `$mod+Entrée`
ouvre un terminal, `$mod+D` le lanceur, `$mod+Maj+Q` ferme une fenêtre,
`$mod+Maj+E` termine la session. `--display sdl` utilise SDL si GTK n'est pas disponible.

## Idées de tests manuels

1. Création du propriétaire : refus d'un mot de passe vide ou différent.
2. `sudo -v` demande ton mot de passe ; le compte root reste verrouillé.
3. `sudo nft list ruleset` montre la politique par défaut.
4. `ip addr` montre une adresse 10.0.2.x obtenue par DHCP. Aucun port de la
   VM n'est exposé sur ton PC.
5. Bureau : ouvrir plusieurs terminaux, changer d'espace de travail,
   lancer une application par le lanceur, quitter la session.
6. Redémarrer (`sudo reboot`), puis vérifier que le compte existe toujours.

Note ce qui casse ou te gêne : c'est exactement ce qu'il faut à ce stade.

## Sécurité de l'essai

`run` ne modifie jamais les images construites : il travaille sur une copie
sous `INT_WORKDIR/run/`. La VM a un réseau sortant en mode utilisateur QEMU,
sans redirection de port. Aucun mot de passe par défaut n'existe.
