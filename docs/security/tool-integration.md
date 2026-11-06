# OS-INT — étude d'intégration des outils

Vérification documentaire du 4 novembre 2026. **Les quatorze outils sont non intégrés et leur consommation mémoire est non mesurée.** Cette étude inventorie des licences, des dépendances et des risques ; elle ne valide aucun paquet, binaire, service ou profil INT. Une bibliothèque éventuellement présente comme dépendance de la base ne constitue pas une intégration OS-INT.

La cible envisagée est Linux x86-64. Le cross-build, le fonctionnement sur INT et la baseline sans AVX/AVX2 restent **non évalués** pour ces outils. Les exigences de langage ci-dessous concernent les sources consultées, pas une version déjà choisie pour INT. Les branches amont mobiles sont citées comme observations datées ; une intégration devra sélectionner une release et figer ses sources et dépendances.

## Inventaire et faisabilité

| Outil — état | Licence vérifiée et redistribution à examiner | Dépendances et runtime principaux | Recette OE vérifiée | Entretien et isolation à prévoir |
| --- | --- | --- | --- | --- |
| **Nmap — non intégré** | NPSL 0.95, licence particulière fondée sur GPLv2 mais incompatible avec elle ; ne pas l'assimiler à GPLv2. Examiner le périmètre de redistribution avant inclusion. [N1] [N3] | C/C++, libpcap, PCRE2 ; Lua et autres bibliothèques peuvent être embarquées ; OpenSSL et fonctions additionnelles selon configuration. [N2] | `meta-oe`, `nmap_7.95.bb`, licence déclarée NPSL. [ON] | Groupe d'inventaire actif optionnel. Périmètre d'évaluation explicite ; sockets brutes seulement avec les droits nécessaires. Les scripts NSE sont du code à inventorier. Suivre aussi les correctifs des composants embarqués. |
| **Wireshark — non intégré** | GPLv2 pour l'ensemble, majorité du code GPL-2.0-or-later et composants compatibles ; certaines utilités ont d'autres licences. [W1] | C/C++, GLib, libpcap, bibliothèques de dissections ; Qt pour l'interface. TShark/dumpcap sont à séparer du paquet graphique. [W2] | `meta-networking`, `wireshark_4.6.8.bb`. Le GUI est désactivé par défaut ; l'option Qt5 de cette recette nécessite une revue de compatibilité avec la version choisie. [OW] | Ne pas exécuter le GUI comme root : limiter les privilèges au helper de capture. Traiter les captures comme des entrées hostiles et sensibles ; retester dissectors et plugins après mise à jour. |
| **tcpdump — non intégré** | BSD-3-Clause ; conserver notices et conditions. [T1] | C et libpcap ; crypto OpenSSL et autres fonctions optionnelles selon recette. [T2] | `meta-networking`, `tcpdump_4.99.6.bb`. [OT] | Capture réseau optionnelle avec privilèges limités ; analyse hors ligne sans privilèges. Les PCAP peuvent contenir secrets et données personnelles. Suivre conjointement tcpdump et libpcap. |
| **OpenSSL — non intégré** | Apache-2.0 pour les sources actuelles ; dépendances et éventuels providers à vérifier séparément. [O1] | Bibliothèques et CLI C, build avec Perl et outils natifs ; options et accélérations CPU à vérifier sur la cible conservatrice. [O2] | OE-Core épinglé : `openssl_3.5.9.bb`. [OO] | La branche 3.5 est LTS selon la politique amont ; suivre ses avis de sécurité et reconstruire les consommateurs nécessaires. Protéger les clés ; installer un paquet ou activer une option ne prouve aucune certification FIPS. [O3] |
| **GnuPG — non intégré** | Le programme amont porte GPL-3.0-or-later ; composants sous LGPL et autres licences. La recette consultée déclare GPL-3.0-only et LGPL-3.0-only : réconcilier les notices au choix exact de version. [G1] | libgcrypt, libgpg-error, libassuan, libksba, npth ; Pinentry pour les opérations usuelles, dépendances supplémentaires selon fonctions. [G2] | OE-Core épinglé : `gnupg_2.5.17.bb`. [OG] | Séparer clés de signature release et clés utilisateur. Contrôler accès au trousseau, sockets de l'agent et récupération des clés ; aucun secret dans l'image ou les logs. Suivre GnuPG et ses bibliothèques. |
| **YARA classique — non intégré** | BSD-3-Clause ; règles et modules peuvent avoir leurs propres licences. [Y1] | C/pthreads, libyara ; OpenSSL et modules libmagic/Jansson selon configuration ; binding Python séparé. [Y2] | Autres couches : **non évalué**. | L'amont déclare le projet en maintenance, avec correctifs critiques/sécurité, et recommande YARA-X pour la suite. Documenter ce coût avant sélection ; aucune substitution faite ici. Scanner des copies en lecture seule, borner ressources et confiance des règles. [Y3] |
| **Zeek — non intégré** | BSD-3-Clause, avec notices particulières pour certains fichiers. [ZK1] | C++20/CMake, libpcap, OpenSSL, zlib, ZeroMQ ; Python et outils natifs pour build/gestion ; extensions/Spicy ajoutent leur chaîne. [ZK2] | Autres couches : **non évalué**. | Capteur défensif facultatif, aucun daemon activé par défaut. Contrôler droits de capture, rétention des logs, scripts et plugins ; préférer une ligne maintenue et suivre sa cadence plutôt que les branches de développement. [ZK3] |
| **Suricata — non intégré** | GPL-2.0-only pour le programme ; licences des règles, plugins et bibliothèques à inventorier. [S1] | C et Rust/Cargo ; libpcap, PCRE2, Jansson, YAML, zlib ; gestion des règles et interfaces additionnelles selon configuration. [S2] | Autres couches : **non évalué**. | IDS/IPS optionnel ; commencer par PCAP hors ligne puis capteur explicite, sans passer automatiquement en IPS. Borner buffers et journaux. Traiter les règles et `suricata-update` comme un flux distinct à vérifier, sans téléchargement automatique non maîtrisé. |
| **theHarvester — non intégré** | Tag 4.11.1 : GPL-2.0-only dans `pyproject.toml`. [H1] | Python ≥3.12 pour ce tag, dépendances HTTP/DNS, SQLite/SQLAlchemy, lxml et Playwright ; le navigateur est un composant séparé. [H1] | Autres couches : **non évalué**. | Groupe OSINT optionnel. Connecteurs fournisseurs, API et browser augmentent le coût de maintenance ; conserver clés et résultats hors image. La politique amont couvre la dernière release et `master`, sans preuve ici d'une fenêtre de backports. [H2] |
| **Amass — non intégré** | Tag v5.1.3 : Apache-2.0 ; auditer modules et notices. [A1] | Ce tag exige Go 1.27.3 ; DNS/HTTP, modèle d'actifs et stockage. **Écart avec Go 1.26.9 de l'OE-Core épinglé.** Ne pas le contourner par un téléchargement automatique de toolchain. [A2] | Autres couches : **non évalué**. | L'outil couvre reconnaissance active et sources publiques : scope et egress explicites. Isoler secrets et bases d'enquête ; suivre modules et adaptateurs. Fenêtre de support formelle : **non évaluée**. |
| **Subfinder — non intégré** | Tag v2.17.0 : MIT. [F1] | Go ≥1.26.0 selon `go.mod`, modules DNS/HTTP et fournisseurs ; présence d'un compilateur compatible ne prouve pas le cross-build. [F3] | Autres couches : **non évalué**. | Les fournisseurs reçoivent les requêtes et peuvent exiger clés, quotas et conditions d'usage. Le CLI possède des fonctions d'auto-update : les remplacer par le flux INT signé ou les désactiver explicitement dans le paquet validé. [F2] |
| **OWASP ZAP — non intégré** | Tag v2.17.0 : Apache-2.0 ; add-ons et navigateurs à inventorier séparément. [P1] | Java ≥17 pour Linux selon l'amont ; build Gradle ; add-ons et navigateur peuvent ajouter des dépendances natives. [P2] | Autres couches : **non évalué**. | Groupe web/lab, mode Protected et périmètre explicite ; proxy/API sur loopback, clé API conservée et profil navigateur dédié. [P4] [P5] Les vérifications d'updates au démarrage et le canal d'add-ons nécessitent une politique INT distincte. [P3] |
| **Ghidra — non intégré** | Tag 12.2 : Apache-2.0 pour le projet, avec notices/licences tierces. [D1] | Le README du tag demande JDK 25 64-bit, Gradle ≥9.1, Python et GCC/Clang+make pour les natifs Linux. Chaîne Java et natifs à construire/valider séparément. [D2] | Autres couches : **non évalué**. | Groupe analyse/lab ; binaires hostiles dans un environnement jetable sans privilèges. Scripts/extensions sont du code, réseau limité. Suivre releases et Security Advisories ; support long terme : **non évalué**. [D3] |
| **Volatility 3 — non intégré** | Tag v2.28.2 : **Volatility Software License 1.0**, licence personnalisée, pas GPL. Son copyleft couvre notamment certains wrappers conçus pour l'exécuter et parser ses résultats ; revue du futur frontend INT requise. [V1] | Python ≥3.8, `pefile` ; extras tels que yara-python, Capstone, PyCryptodome/LeechCore ; tables de symboles et cache à gérer. [V2] [V4] | Autres couches : **non évalué**. | Groupe mémoire/lab ; dumps sensibles hors ligne et en lecture seule, plugins et symboles contrôlés. Les téléchargements de symboles doivent être explicites. Volatility 2 est archivé/Python2 : aucun remplacement par cette branche legacy. [V3] |

## Portée des recettes et licences

Les recettes vérifiées proviennent de l'OE-Core déjà épinglé par INT (`ae5a301091f5b0574ea7444aab40b309b6d9f3f2`) et de l'arbre `meta-openembedded/wrynose` observé à `c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e`. Cette dernière couche **n'a pas été ajoutée à INT**. L'inventaire de cet arbre est complet pour cette observation ; les autres couches de l'écosystème, leurs dépendances et leurs licences restent **non évaluées**. L'existence d'une recette n'établit ni son état de sécurité, ni sa réussite au build, ni la disponibilité de son interface graphique.

Les licences permissives restent assorties d'obligations de notices, et Apache-2.0 comporte des dispositions spécifiques, dont les brevets et les notices applicables. Les composants GPL/LGPL nécessitent une gestion des sources correspondantes, des modifications et des obligations de redistribution. NPSL et VSL demandent une revue spécifique ; l'étude ne vaut pas acceptation automatique de leurs conditions. Les règles IDS/YARA, bases d'intelligence, profils mémoire, plugins et données des fournisseurs ont leur propre statut. Un nom de licence dans une recette ne remplace pas la revue des fichiers de la release choisie.

## Groupes facultatifs et maintenance

- **Crypto et signature :** OpenSSL/GnuPG, uniquement pour les usages et dépendances nécessaires ; pas de duplication de bibliothèques ou de clés privées préinstallées.
- **Capture et défense réseau :** tcpdump/TShark d'abord, GUI Wireshark séparé ; Zeek et Suricata comme services facultatifs configurés explicitement. Aucune collecte permanente dans l'image de base.
- **Recherche OSINT et inventaire autorisé :** theHarvester, Amass, Subfinder, Nmap. Une source publique ne rend pas toutes les requêtes passives ; permissions, scope, quotas et conditions fournisseurs restent explicites.
- **Laboratoire web et analyse :** ZAP, YARA, Ghidra, Volatility 3 ; copies d'entrées, stockage des preuves séparé, privilèges réduits et isolation jetable selon le risque.

Pour chaque intégration, INT doit figer release, sources, dépendances et règles ; vérifier les artefacts amont ; produire licence/SBOM/provenance ; construire depuis les sources et tester le paquet sur INT. Les flux Python, Go, Gradle, browsers, plugins et règles ne doivent pas contourner ce processus par des installateurs distants ou des binaires téléchargés automatiquement. Les dépôts binaires d'une autre distribution et les conteneurs Debian/Ubuntu proposés par certaines documentations amont ne deviennent pas des dépendances de la rootfs INT.

Mesurer ensuite consommation au repos et en charge sur un corpus, une capture ou un dump identifiés, avec limites de temps, mémoire et stockage. Aucune valeur chiffrée ni minimum matériel n'est déduit de cette étude. Vérifier les chemins natifs et JIT sur la baseline CPU sans AVX, et maintenir un test de régression pour chaque groupe avant de cocher son intégration.

## Sources consultées

Les identifiants du tableau sont des liens directs vers les licences, fichiers de build, politiques et recettes consultés. Les sources principales sont [Nmap][N1], [Wireshark][W1], [tcpdump][T1], [OpenSSL][O1], [GnuPG][G1], [YARA][Y1], [Zeek][ZK1], [Suricata][S1], [theHarvester][H1], [Amass][A1], [Subfinder][F1], [ZAP][P1], [Ghidra][D1] et [Volatility 3][V1].

[N1]: https://github.com/nmap/nmap/blob/master/LICENSE
[N2]: https://nmap.org/book/inst-source.html
[N3]: https://github.com/nmap/nmap/blob/master/README.md
[W1]: https://github.com/wireshark/wireshark/blob/master/README.md#license
[W2]: https://github.com/wireshark/wireshark/blob/master/CMakeLists.txt
[T1]: https://github.com/the-tcpdump-group/tcpdump/blob/master/LICENSE
[T2]: https://github.com/the-tcpdump-group/tcpdump/blob/master/INSTALL.md
[O1]: https://github.com/openssl/openssl/blob/master/LICENSE.txt
[O2]: https://github.com/openssl/openssl/blob/master/INSTALL.md
[O3]: https://openssl-library.org/policies/releasestrat/
[G1]: https://github.com/gpg/gnupg/blob/master/g10/gpg.c
[G2]: https://github.com/gpg/gnupg/blob/master/README
[Y1]: https://github.com/VirusTotal/yara/blob/master/COPYING
[Y2]: https://github.com/VirusTotal/yara/blob/master/configure.ac
[Y3]: https://virustotal.github.io/yara-x/blog/yara-x-is-stable/
[ZK1]: https://github.com/zeek/zeek/blob/master/COPYING
[ZK2]: https://github.com/zeek/zeek/blob/master/doc/building-from-source.rst
[ZK3]: https://github.com/zeek/zeek/blob/master/doc/install.rst
[S1]: https://github.com/OISF/suricata/blob/main/src/suricata.c
[S2]: https://docs.suricata.io/en/latest/install.html
[H1]: https://github.com/laramies/theHarvester/blob/4.11.1/pyproject.toml
[H2]: https://github.com/laramies/theHarvester/blob/master/SECURITY.md
[A1]: https://github.com/owasp-amass/amass/blob/v5.1.3/LICENSE
[A2]: https://github.com/owasp-amass/amass/blob/v5.1.3/go.mod
[F1]: https://github.com/projectdiscovery/subfinder/blob/v2.17.0/LICENSE.md
[F2]: https://github.com/projectdiscovery/subfinder/blob/v2.17.0/README.md
[F3]: https://github.com/projectdiscovery/subfinder/blob/v2.17.0/go.mod
[P1]: https://github.com/zaproxy/zaproxy/blob/v2.17.0/LICENSE
[P2]: https://github.com/zaproxy/zaproxy-website/blob/main/site/data/download/c_main.yml
[P3]: https://github.com/zaproxy/zaproxy/blob/v2.17.0/zap/src/main/java/org/zaproxy/zap/extension/autoupdate/OptionsParamCheckForUpdates.java
[P4]: https://github.com/zaproxy/zaproxy-website/blob/main/site/content/docs/desktop/start/features/modes.md
[P5]: https://github.com/zaproxy/zaproxy-website/blob/main/site/content/docs/desktop/start/features/api.md
[D1]: https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.2_build/LICENSE
[D2]: https://github.com/NationalSecurityAgency/ghidra/blob/Ghidra_12.2_build/README.md
[D3]: https://github.com/NationalSecurityAgency/ghidra/security/advisories
[V1]: https://github.com/volatilityfoundation/volatility3/blob/v2.28.2/LICENSE.txt
[V2]: https://github.com/volatilityfoundation/volatility3/blob/v2.28.2/pyproject.toml
[V3]: https://github.com/volatilityfoundation/volatility/blob/master/README.txt
[V4]: https://github.com/volatilityfoundation/volatility3/blob/v2.28.2/README.md
[ON]: https://git.openembedded.org/meta-openembedded/tree/meta-oe/recipes-security/nmap/nmap_7.95.bb?id=c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e
[OW]: https://git.openembedded.org/meta-openembedded/tree/meta-networking/recipes-support/wireshark/wireshark_4.6.8.bb?id=c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e
[OT]: https://git.openembedded.org/meta-openembedded/tree/meta-networking/recipes-support/tcpdump/tcpdump_4.99.6.bb?id=c734c2cb9713dbd6d50697a9f6c25ebdf3ae589e
[OO]: https://git.openembedded.org/openembedded-core/tree/meta/recipes-connectivity/openssl/openssl_3.5.9.bb?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2
[OG]: https://git.openembedded.org/openembedded-core/tree/meta/recipes-support/gnupg/gnupg_2.5.17.bb?id=ae5a301091f5b0574ea7444aab40b309b6d9f3f2

Les références ci-dessus sont utilisées dans le tableau ; aucun outil n'a été installé ni exécuté pour cette étude. Les pages directes ZAP ayant refusé la requête, les sources de son site officiel ont servi à vérifier les exigences Java. Les résultats de cette recherche documentaire ne cochent aucune validation runtime.
