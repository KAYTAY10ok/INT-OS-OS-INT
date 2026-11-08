# INT Linux sur clé USB (live + installation) — version de développement

Ce n'est **pas** une version finie ni publiée. Utilise un **PC de test** :
écrire la clé efface la clé, et l'option « install » efface **tout** le
disque choisi.

## 1. Obtenir l'ISO

Construis-la (voir [COMPILER-SOUS-WINDOWS.md](COMPILER-SOUS-WINDOWS.md)) :

```bash
./scripts/int --profile live configure
```

```bash
./scripts/int --profile live build
```

Le fichier est `~/int-linux-work/build-live/tmp/deploy/images/qemux86-64/int-image-live-qemux86-64.rootfs.iso`
(environ 1,7 Go).

## 2. Écrire la clé (Windows)

- **balenaEtcher** (le plus simple) : « Flash from file », choisis l'ISO (ou
  le `.iso.xz`, pas besoin de décompresser), choisis la clé, « Flash ».
- **Rufus** : choisis l'ISO puis, à la question, « Écrire en mode image DD ».

## 3. Démarrer le PC de test sur la clé

Dans le BIOS/UEFI (F2, F10, F12, Suppr ou Échap selon la marque) :
désactive **Secure Boot** (pas encore pris en charge), puis démarre sur la clé
(menu de démarrage, souvent F12 ou F8). Menu GRUB :

- **boot** : INT Linux tourne depuis la clé ; rien n'est installé, tout est
  perdu à l'arrêt.
- **install** : installateur en français ou en anglais. On répond par des
  **numéros** : langue, clavier (Suisse romand, France, Suisse alémanique,
  US, Belgique), édition (**INT-OS** minimaliste ou **OS-INT** cyber/opsec),
  chiffrement du disque (LUKS2 : phrase secrète invisible, tapée deux fois,
  demandée à chaque démarrage), IA locale (aucune / petite / grande,
  téléchargée au premier démarrage), disque, puis on **retape le numéro du
  disque** pour confirmer (0 = annuler, rien n'est touché). Le disque choisi
  est entièrement effacé. À la fin, retire la clé et appuie sur Entrée.

## 4. Premier démarrage du système installé

1. Crée ton compte (nom en minuscules, mot de passe deux fois). Il n'existe
   aucun mot de passe par défaut et root est verrouillé.
2. Connecte-toi sur la première console : le bureau démarre tout seul
   (`int-session autostart off` pour l'arrêter ; sinon `start-int-desktop`).
3. La première fois, choisis :
   - le **thème** : anime, blue, dark, light, pink (plus tard : Super+t) ;
   - tes **groupes d'applications** (plus tard : `int-apps choose`) :

| Groupe | Contenu | Par défaut |
| --- | --- | --- |
| Cyber / réseau | nmap, tcpdump, tshark, socat, netcat, traceroute | OS-INT |
| Opsec / vie privée | Tor, macchanger, WireGuard, OpenVPN, exiftool, GnuPG | OS-INT |
| Outils terminal | htop, btop, nano, tmux, zsh, rsync, unzip | OS-INT |
| Outils du bureau | captures d'écran, presse-papiers, notifications, verrouillage, luminosité | les deux |
| Audio | son PipeWire + WirePlumber (le retirer coupe le son) | les deux |
| Développement | git, make, strace, gdb | — |
| Navigateur, multimédia | Firefox, mpv | dépôt INT requis (pas encore disponible) |

Les groupes non choisis sont retirés du disque après confirmation (ton mot
de passe est demandé). Le chiffrement et le système de base ne sont jamais
retirés.

## 5. Raccourcis

| Touches | Action |
| --- | --- |
| Super+Entrée | terminal |
| Super+D | lanceur d'applications |
| Super+I | tableau de bord |
| Super+T | changer de thème |
| Impr écran / Super+Impr | capture d'écran (écran entier / zone) dans `~/Images` |
| Super+Échap | verrouiller l'écran |
| Super+Maj+Q | fermer la fenêtre |
| Super+Maj+E | quitter le bureau |

Éteindre : `sudo poweroff`.

## 6. Commandes utiles

- `int-ai mets le theme rose`, `int-ai etat du systeme` : IA locale (les
  thèmes et la lecture sans confirmation, tout le reste est confirmé).
- `int-apps list` : état des groupes d'applications.
- `int-privacy status`, `sudo int-privacy tor on` (OS-INT).
- `int-theme wallpaper ~/mon-image.png` : ton fond d'écran.

## Limites de cette version

Pas d'accélération 3D (affichage logiciel), NVIDIA non pris en charge,
installation sur disque entier seulement, pas encore de dépôt de paquets,
Hyprland et Firefox pas encore inclus. Wi-Fi, son et pavé tactile **pas
encore testés sur vrai matériel** : note le modèle du PC et ce qui marche ou
pas, c'est la priorité suivante. L'installateur crée une entrée « INT Linux »
dans le firmware ; si le PC démarre ailleurs, choisis le disque dans son
menu de démarrage.
