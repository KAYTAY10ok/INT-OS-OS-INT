# Mission Claude — dépôt RPM signé et mises à jour en VM

Ce document délègue à Claude la majeure partie du chantier de gestion de
paquets actuellement en cours. Il est destiné à être utilisé dans ce dépôt,
avec accès au même répertoire de travail. L'objectif est de produire un jalon
fonctionnel et vérifié, puis de documenter honnêtement ses limites. Ne présente
pas INT Linux comme un système terminé ni comme une version prête à publier.

## Mission et périmètre

Prends en charge de bout en bout le laboratoire de signatures, les paquets de
test, les dépôts jetables, l'image QEMU expérimentale et les scénarios DNF
d'acceptation et de rejet. Corrige les défauts réellement rencontrés, ajoute
les tests nécessaires et conserve les preuves. Les instructions détaillées et
les interfaces existantes se trouvent dans :

- [Plan de signature](signed-feed-plan.md) : chaîne de confiance, limites et
  exigences de vérification.
- [Paquets de test](feed-probe.md) : deux versions du petit paquet à construire.
- [Génération des dépôts jetables](feed-fixtures.md) : entrées, variantes et
  contraintes du générateur.
- [Plan de la VM DNF](feed-vm-plan.md) : transport, isolation et cas à tester.
- [Passation générale](../../CLAUDE_HANDOFF.md),
  [instructions de compilation](../../BUILDING.md) et
  [spécification du projet](../PROJECT_SPECIFICATION.md) : contexte et
  architecture. Certains passages historiques peuvent être dépassés ; utilise
  les journaux et les validations les plus récents pour déterminer l'état réel.

L'utilisateur a autorisé les commits et pushes GitHub du travail demandé. Ne
publie ni release, ni dépôt de paquets, ni environnement cloud. Ne force pas
le push. Conserve les modifications existantes et les fichiers non suivis :
inspecte leur provenance avant de les modifier ou de les ajouter.

## État constaté lors de la passation

- Le noyau console et le bureau Sway ont déjà des validations QEMU séparées ;
  ce sont des jalons partiels. La dernière validation graphique inclut le
  clavier virtuel et le lanceur ; voir
  [validation graphique](validation-graphics-2026-11-06.md). Le matériel
  physique et le produit complet restent à qualifier.
- Le profil `feed` utilise `build-feed`, distinct de `build` et
  `build-desktop`. Le contrôle de configuration a confirmé `sequoia` dans
  `PACKAGECONFIG` pour `rpm-native` et `rpm` cible. Voir
  `/workspace/int-linux-work/check-feed.log`.
- La compilation de `rpm-native` avec ses dépendances Sequoia a réussi :
  920 tâches, aucune erreur. Journal :
  `/workspace/int-linux-work/build-rpm-sequoia.log`. Une compilation réussie
  **ne prouve pas** que les signatures sont effectivement vérifiées.
- Le laboratoire `int-feed-lab-native` est lancé ; son journal est
  `/workspace/int-linux-work/feed-lab-20261106-native.log`. Il n'a pas encore
  fourni de résultat de signature au moment de cette passation. Vérifie le
  verrou, les processus et ce journal avant toute opération. Le générateur de
  fixtures existe également, mais son résultat avec les vrais outils natifs
  reste à établir.
- `int-feed-probe` existe en versions `1.0` et `2.0`, et
  `int-image-feed-smoke` existe comme recette expérimentale. Aucune installation
  ni mise à jour DNF en VM n'a encore été démontrée à cette date. L'image ne
  contient pas encore le service de test ; malgré son nom, elle n'exécute pas
  encore de smoke test.
- Les 87 tests hôte de la suite existante ont réussi ; journal
  `/workspace/int-linux-work/host-tests-fixtures.log`. Ils ne remplacent pas
  les tests natifs et invités.
- `scripts/feed-disk.py` prépare un disque EXT4 à partir de fixtures contrôlées
  par leur manifeste. Ses cinq tests passent dans le conteneur, y compris la
  création et la lecture d'une image synthétique. Il ne vérifie pas les
  signatures et n'a pas été utilisé avec QEMU ou les fixtures signées réelles ;
  voir [feed-disk.md](feed-disk.md).
- Les preuves et caches volumineux sont hors dépôt, sous
  `/workspace/int-linux-work`. Leur présence et l'espace libre doivent être
  revérifiés ; ne supprime pas arbitrairement des données ou caches existants.

Cet état est une photographie, pas un verrou ni une promesse que tous les
processus ont fini. Quelqu'un peut poursuivre le travail en parallèle :
coordonne-toi avant de modifier les mêmes fichiers ou de démarrer une tâche.

## Première action : établir le contexte réel

Depuis `/workspace/INT-OS-OS-INT`, relève sans exposer de secrets :

```sh
git status --short
git log -5 --oneline
git ls-remote --heads origin main
ps -eo pid,etime,args | rg 'bitbake|scripts/int|int-feed-lab'
tail -30 /workspace/int-linux-work/build-rpm-sequoia.log
df -h /workspace
```

Regarde aussi les journaux `feed-lab-*.log` sous `/workspace/int-linux-work`
et les fichiers modifiés ou non suivis. Si une compilation ou un test est
actif, laisse-le se terminer, surveille son résultat et évite une deuxième
opération BitBake dans ce répertoire de travail. `scripts/int` prend un verrou
non bloquant ; n'essaie pas de le contourner avec un autre conteneur. Une
interruption passée a laissé des objets compilés corrompus. En cas d'échec,
préserve les journaux et diagnostique avant de relancer. Ne lance pas de
nettoyage destructif pour récupérer de l'espace.

## Lot 1 — signatures natives réelles

Après la fin de toute opération active, si le laboratoire n'a pas déjà été
exécuté avec succès, lance depuis le dépôt :

```sh
set -o pipefail
./scripts/int --profile feed build int-feed-lab-native 2>&1 | \
  tee "/workspace/int-linux-work/feed-lab-$(date -u +%Y%m%dT%H%M%SZ).log"
```

Corrige les erreurs de recette, de sysroot ou d'interaction entre les outils
en t'appuyant sur leurs sorties réelles, puis relance et garde les deux
journaux. Le résultat doit prouver une vraie signature RPM valide et le rejet
d'une clé absente ou incorrecte, d'un paquet altéré et d'un paquet non signé
avec une politique exigeant des signatures. Il doit aussi vérifier la
signature de `repomd.xml` et les cas négatifs prévus. L'acceptation d'un simple
digest n'est pas une signature. Vérifie le code de retour et les messages
machine pertinents ; un échec sans rapport ne doit pas valider un cas négatif.

Le laboratoire crée uniquement des clés de test éphémères, non protégées et à
expiration courte. Ne réutilise jamais ces clés pour une livraison. Les
secrets de production ne doivent entrer ni dans les arguments, ni dans les
journaux, les métadonnées BitBake, les caches ou Git. Les outils natifs doivent
être exécutés dans leur sysroot OE complet, pas en assemblant des exécutables
pris au hasard dans plusieurs répertoires.

## Lot 2 — fixtures et image expérimentale

1. Construis séparément les deux versions de `int-feed-probe` et copie les RPM
   non signés avant que la seconde construction puisse modifier le répertoire
   de déploiement. Suis exactement [feed-probe.md](feed-probe.md), dans le
   shell du profil `feed` et une fois le verrou libre.
2. Exécute ensuite la tâche optionnelle `create_feed_fixtures` conformément à
   [feed-fixtures.md](feed-fixtures.md). Elle signe des copies, crée des
   variantes positives et négatives et produit son manifeste uniquement après
   nettoyage ordinaire des clés temporaires. Vérifie réellement la sortie ;
   une génération interrompue sans manifeste n'est pas un succès. Un arrêt
   brutal peut laisser des clés jetables sous `/tmp` : inspecte avant tout
   nettoyage ciblé, et ne prétends pas à un effacement sécurisé.
3. Construis l'image expérimentale avec
   `./scripts/int --profile feed build int-image-feed-smoke` après les autres
   opérations. Inspecte son manifeste : RPM avec Sequoia, DNF, GnuPG requis,
   noyau et espace disque doivent correspondre aux tests prévus. Une image
   construite ne démontre ni démarrage ni politique de signature.
4. Implémente et vérifie le transport du dépôt local vers QEMU et le service
   de test isolé décrits dans [feed-vm-plan.md](feed-vm-plan.md). Un outil de
   disque existe mais doit encore être intégré et validé avec QEMU :
   inspecte `git status` avant de créer ou remplacer quoi que ce soit. Monte
   le disque de fixtures en lecture seule, sans clé privée et sans port réseau
   exposé ; protège les entrées et conserve leurs empreintes avant et après.

## Lot 3 — vraie validation DNF en invité

Utilise un dépôt `file://` uniquement, une clé publique de test et une
empreinte complète fournie indépendamment du disque de dépôt. Vérifie cette
empreinte avant l'import. Isole les trousseaux, caches et configurations de
chaque cas. Désactive les autres dépôts et impose `gpgcheck=1`,
`repo_gpgcheck=1`, `localpkg_gpgcheck=1` et `skip_if_unavailable=0`. Ne passe
pas `--nogpgcheck`.

Sur une VM jetable : vérifie les métadonnées, installe la version `1.0`, mets
à jour vers `2.0`, vérifie à chaque fois la base RPM et le fichier installé,
puis répète la mise à jour pour vérifier l'idempotence. Exige arrêt propre,
marqueurs stricts, résultat QEMU et preuves conservées.

Avec un état initial valide et un cache/confiance isolé pour chaque cas,
exige un refus motivé et la conservation de la version et du fichier installés :

- clé de dépôt absente ou incorrecte, signature de métadonnées absente ou
  altérée, `repomd.xml` modifié, métadonnées référencées modifiées ;
- RPM altéré ou somme incorrecte ;
- RPM non signé, signé par une autre clé ou corrompu, avec métadonnées
  fraîchement indexées et correctement signées, afin d'atteindre le contrôle
  du RPM ;
- base de confiance RPM vide et moteur OpenPGP inutilisable, avec un contrôle
  positif séparé qui prouve que le backend sait réellement vérifier.

Capture codes de retour, diagnostics limités, empreintes, versions des outils,
hashes des artefacts et état installé. Un échec provoqué par un fichier
manquant, une dépendance, un cache ou une autre cause ne valide pas le rejet de
signature recherché. La matrice complète et les limites sont dans
[signed-feed-plan.md](signed-feed-plan.md).

## Lot 4 — finalisation et suite du projet

- Exécute les tests adaptés aux modifications, y compris
  `python3 -m unittest discover -s tests`, puis les vrais tests natifs et QEMU.
  Consigne précisément les commandes, résultats, chemins de preuves et limites.
- Préserve les images console et bureau validées et leur séparation des
  assistants de test. Aucun mot de passe par défaut, déverrouillage de root ou
  service distant ne doit être introduit pour faciliter les essais.
- Après un jalon vérifié, mets à jour les documents concernés, vérifie
  `git diff --check`, crée des commits cohérents et pousse en avance rapide sur
  `origin` branche `main`, conformément à l'autorisation utilisateur. Avant le
  push, inspecte `git status` et la branche distante ; ne pousse ni clés privées,
  caches, journaux sensibles, fichiers involontaires ni artefacts volumineux.
- Signale clairement ce qui fonctionne, ce qui a échoué et ce qui reste à
  faire. Une signature valide ne règle pas la fraîcheur du dépôt, la prévention
  du rejeu, la rotation des clés ou la récupération après interruption. Le
  réseau, la publication, le stockage des clés de production, l'installateur,
  la sécurité complète, le matériel physique et les performances restent des
  chantiers distincts. Ne prétends pas avoir terminé l'OS.

Poursuis ensuite les autres étapes de la spécification par petits jalons
vérifiables, en conservant une architecture partagée INT-OS / OS-INT. Si une
action dépend d'un secret, d'un accès indisponible ou d'une décision produit
essentielle, expose précisément le blocage et termine le travail indépendant.

## Avancement 2026-11-06

- Ajouté : le paquet de test `int-feed-smoke`
  (`meta-int/recipes-test/int-feed-smoke`), installé uniquement dans
  `int-image-feed-smoke`. Un démarrage exécute un seul cas DNF (mise à jour
  valide et idempotence, ou l'un des dix cas de rejet), lit l'empreinte
  attendue sur la ligne de commande du noyau (`int.feed_fpr`), monte le disque
  de fixtures `INTFEED` en lecture seule (`nosuid,nodev,noexec,noload`),
  vérifie une signature `rpmkeys` valide et le rejet `NOKEY` avec une base de
  confiance vide, puis éteint la VM.
- Ajouté : `scripts/qemu-feed-check.py` et
  `./scripts/int --profile feed feed-check /work/feed-disks/NAME --fingerprint FPR --feed-sha256 SHA [--case NAME]...`.
  Pas de carte réseau, disque racine en instantané, disque de fixtures en
  `readonly=on` et vérifié par hash avant et après chaque cas.
  `INT_DOCKER_NETWORK=host` est documenté dans [BUILDING.md](../../BUILDING.md).
  Procédure exacte : [feed-vm-plan.md](feed-vm-plan.md).
- **Rien n'a encore été construit ni démarré** : image, laboratoire natif
  `int-feed-lab-native`, paquets de test et fixtures restent à produire ; une
  compilation de `int-feed-lab-native` est en cours. Les diagnostics DNF
  attendus proviennent d'une répétition sur l'hôte avec les outils Ubuntu
  24.04 (DNF 4.14, RPM 4.18, createrepo_c 0.17.3, GnuPG 2.4.4), où le
  générateur et les onze cas ont réussi. Ce n'est pas une preuve OE ni invité :
  à confirmer avec DNF 4.24 et RPM 4.20.1 + Sequoia d'OE.
- Limites connues : aucun cas avec moteur OpenPGP RPM désactivé (seul le
  contrôle positif existe) ; les clés de laboratoire expirent après un jour,
  donc fixtures, disque et exécutions VM doivent tenir dans ce délai ;
  fraîcheur/rejeu, rotation des clés, reprise après interruption, transport
  réseau et garde des clés de production restent hors périmètre.
