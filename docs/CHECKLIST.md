# INT Linux — checklist (fait / reste à faire)

État au 2026-11-08. Version de développement : **le système n'est pas fini**
et n'est publié nulle part. « Validé » = testé dans QEMU (PC UEFI virtuel),
**pas encore sur un vrai PC** sauf mention contraire.

## Fait

### Base, paquets, outils de construction
- [x] Distribution Yocto/OE « wrynose » : profils core, desktop, feed, live, browser (`scripts/int`)
- [x] Laboratoire RPM signé, paquets et fixtures de test, tests DNF accepte/refuse (avec Codex)
- [x] Clés de test éphémères, aucune clé ni aucun secret dans Git
- [x] `./scripts/int run` : essai dans QEMU sur une copie de l'image
- [x] Guide de compilation sous Windows / WSL2 (`docs/COMPILER-SOUS-WINDOWS.md`)

### Démarrage réel et installateur
- [x] ISO live UEFI (clé USB) pour PC Intel/AMD, pilotes graphiques/Wi-Fi/réseau et firmwares — validé QEMU
- [x] Session live en lecture seule (overlay en mémoire)
- [x] Installateur FR/EN par numéros : langue, clavier (fr_CH, fr, de_CH, us, be), édition INT-OS/OS-INT, chiffrement, IA, disque, double confirmation
- [x] Chiffrement complet du disque LUKS2 (phrase invisible, tapée deux fois, demandée au démarrage) — validé QEMU
- [x] Entrée de démarrage « INT Linux » dans le firmware (efibootmgr)
- [x] Premier démarrage : création du compte propriétaire, pas de mot de passe par défaut, root verrouillé

### Éditions
- [x] OS-INT cyber/réseau : nmap, tcpdump, tshark, socat, netcat, traceroute — validé QEMU
- [x] OS-INT opsec : Tor (désactivé par défaut, `int-privacy tor on`), WireGuard, OpenVPN, macchanger, exiftool, GnuPG, adresse MAC aléatoire, durcissement noyau (sysctl, Yama)
- [x] Recette Tor depuis les sources officielles
- [~] Secure Boot par MOK : recettes et script de signature écrits, **pas validé** (source du shim à décider)

### Bureau et look
- [x] Bureau Sway : terminal foot, lanceur fuzzel
- [x] Thèmes dark, light, blue, pink, anime (`int-theme`, Super+t), choix au 1er démarrage du bureau
- [x] Fonds d'écran générés par thème, ou image personnelle (`int-theme wallpaper`)
- [x] Gros logo ASCII INT affiché dans chaque terminal (fastfetch)
- [x] Barre d'état colorée : CPU, RAM, disque, réseau, batterie, heure — validé QEMU
- [x] Tableau de bord flottant translucide (Super+i)
- [x] Configuration Hyprland écrite + choix du moteur (`int-session sway|hyprland`) — **pas encore construite ni testée**

### Groupes d'applications (presets)
- [x] `int-apps` : groupes cyber, opsec, terminal, outils du bureau, développement (sur l'ISO) ; navigateur, audio, multimédia (dépôt INT)
- [x] Choix au 1er démarrage du bureau sur un système installé ; les groupes non choisis sont retirés hors ligne après confirmation ; cryptsetup et le système de base jamais retirés
- [x] Raccourcis des outils du bureau : Impr écran, Super+Impr (zone), Super+Échap (verrouillage), luminosité
- [x] Tests sur l'hôte (15) ; ISO construite avec dnf/rpm et les paquets des groupes
- [x] Validé QEMU : installation OS-INT, choix des applications au 1er démarrage, retrait hors ligne, vérifié après redémarrage (`docs/development/validation-apps-presets-2026-11-08.md`)

### IA locale « super commande »
- [x] `int-ai` : llama.cpp + Qwen2.5 (taille choisie à l'installation : aucune / 1.5B / 7B, téléchargement au 1er démarrage)
- [x] Sans confirmation : lecture (état du système, fichiers, thèmes, liste des apps) et changement de thème
- [x] Toujours confirmé : création de fichiers, installation/retrait d'applications, vérification de sécurité
- [x] Refus déterministe des demandes destructrices (supprimer, formater…) avant même le modèle
- [x] Validé QEMU : « mets le thème bleu » change tout le bureau

## Reste à faire

### Priorité 1 — vrai matériel
- [x] `int-wifi` (scan, connexion avec mot de passe caché, DHCP sans fil) — testé sur l'hôte seulement, **pas de carte Wi-Fi en QEMU** : à essayer sur un vrai PC
- [ ] **Essai sur un vrai PC** (clé USB) : démarrage, Wi-Fi, son, pavé tactile, écran — retour du propriétaire attendu
- [x] Guide de la clé USB dans le dépôt (`docs/CLE-USB.md`)
- [x] ISO 0.5 livrée au propriétaire (2026-11-08, commit 3276be6, SHA-256 ISO 6294fc10…0e1eb8) ; aide Super+F1 vérifiée en QEMU
- [ ] NVIDIA (plus tard)

### Priorité 2 — bureau complet
- [ ] Construire et tester **Hyprland** (machine ≥ 150 Go : WSL2 du propriétaire ou Codex)
- [ ] Construire **Firefox** (meta-browser) sur la même grande machine
- [ ] Choix Sway/Hyprland proposé à l'installation pour INT-OS
- [ ] Fonds d'écran anime sous licence libre (CC0/CC-BY, source notée) ou fournis par le propriétaire
- [ ] Supprimer `themeExemple/` quand le propriétaire valide les thèmes
- [x] Son PipeWire + WirePlumber (groupe « Audio », par défaut) — validé QEMU (carte Intel HDA virtuelle)
- [ ] Son sur vrai PC, compatibilité PulseAudio (pipewire-pulse), touches de volume
- [ ] Accélération 3D ; aujourd'hui affichage logiciel seulement
- [x] Bureau lancé automatiquement après connexion sur la 1re console d'un système installé (`int-session autostart off|on`) — validé QEMU
- [x] Choix Sway/Hyprland au 1er démarrage du bureau quand Hyprland est installé

### Priorité 3 — paquets et sécurité
- [ ] Dépôt de paquets INT signé (Codex) : il débloque les groupes navigateur/audio/multimédia et les mises à jour
- [ ] Mode d'installation du fichier dépôt et de sa clé sur un système installé (à décider avec Codex)
- [ ] Secure Boot MOK : choisir la source du shim, valider sur un vrai PC
- [ ] torsocks : la source officielle (gitlab.torproject.org) est bloquée par le réseau de la session cloud ; à faire sur une autre machine
- [ ] Installation à côté de Windows (double démarrage) : non prévu pour l'instant

## Limites connues
- Installation sur disque entier seulement ; le disque choisi est effacé.
- OVMF (firmware virtuel) oublie parfois l'entrée « INT Linux » ; sur vrai PC, choisir le disque dans le menu de démarrage si besoin.
- Aucun dépôt de paquets configuré : `int-apps` le dit et n'installe rien depuis le réseau.
- Le disque de la session cloud est petit : les gros composants (Hyprland, Firefox, LLVM/Rust) doivent être construits ailleurs.
