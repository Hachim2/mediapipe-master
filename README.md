# Visage animé sur Raspberry Pi 5

Le programme suit les yeux et la bouche avec MediaPipe et affiche la caméra
ainsi que le visage animé dans une fenêtre OpenCV. Le rendu à points lumineux
reste un effet visuel à l'écran. Aucune donnée n'est envoyée à un microcontrôleur
ou à une matrice LED physique.

## Borne tactile

La nouvelle interface se lance avec **`kiosk.py`**. L'animation faciale historique
reste accessible avec `face_landmarks_camera.py`, sans changement de commande.
Lancer un seul de ces programmes à la fois : ils utilisent la même caméra.

Tkinter fournit ici l'interface locale avec une mise en page redessinée selon
les dimensions de l'écran : boutons larges, palette contrastée, logos PNG
transparents et portrait central. Il réutilise l'environnement graphique existant
et n'exige ni navigateur, ni serveur web, ni accélération graphique particulière.
Les mises à jour Tk et les objets `PhotoImage` restent dans le fil graphique.
La caméra et MediaPipe tournent dans un processus séparé ; les logos, le cartoon
et l'envoi CUPS sont chargés ou exécutés en arrière-plan.

### Installation et lancement

Sur Raspberry Pi OS avec bureau, utiliser l'environnement Python décrit plus bas
(Bookworm 64 bits / Python 3.11 pour les versions MediaPipe épinglées), puis :

```bash
sudo apt install python3-tk
source .venv/bin/activate
python -m pip install -r requirements-kiosk.txt
python kiosk.py --windowed
```

Pour la borne : `python kiosk.py --fullscreen`. `F11` bascule le plein écran ;
`Échap` revient en fenêtre pour la maintenance, puis fermer la fenêtre normalement.
Le tactile doit produire les événements de clic du système graphique. La taille
et l'orientation peuvent changer pendant l'exécution ; minimum de fenêtre 480 ×
480, avec agencement paysage (portrait à gauche, boutons à droite) ou vertical.
Privilégier un écran d'au moins 600 × 800 / 800 × 600 pour la lisibilité publique.

Sous Windows, avec le même venv, les commandes `python kiosk.py --windowed` et
`python kiosk.py --demo` fonctionnent aussi. Tk/Tcl doit être inclus dans
l'installation Python. Pour démarrer sans console en exploitation, utiliser
un lanceur du bureau (ou `pythonw.exe kiosk.py` sous Windows) ; ne pas masquer
les erreurs pendant la configuration initiale.

### Parcours visiteur

1. Logo de lancement pendant **4 secondes** par défaut, réglable de 3 à 5 s.
   Si le matériel n'est pas prêt, un message de chargement reste visible.
2. Accueil avec le deuxième logo, sans flux vidéo : « Placez-vous devant la caméra ».
   Plusieurs visages, un visage trop petit ou mal cadré empêchent la progression.
3. Après stabilisation, grand retour caméra, délai pour se voir, puis **3, 2, 1**.
   Un déplacement, une disparition ou une image ancienne annule la prise de vue.
4. Capture propre, flash bref, traitement cartoon existant et aperçu du tirage.
5. **Impression**, **Dessin** ou **Reprendre la photo**. Dessin affiche uniquement
   « Le dessin robotisé sera bientôt disponible » ; aucune commande de bras n'est envoyée.
6. Après un envoi accepté, **Terminer** ou retour automatique à l'accueil.
   L'interface efface l'ancien aperçu. Le visiteur doit quitter le champ pendant
   une seconde, ou choisir **Nouveau portrait**, avant un nouveau déclenchement.

L'impression utilise la file et les options `PRINTER_QUEUE` / `PRINTER_OPTIONS`
décrites dans la section SELPHY. Seul le tirage de la session courante est envoyé.
Le bouton n'est plus actif pendant l'envoi ; le verrou persistant du module CUPS
reste applicable. « Travail accepté par CUPS » ne confirme pas la sortie physique.
En cas d'erreur avant envoi, le portrait reste affiché et **Réessayer** est proposé.
Si un envoi a déjà été tenté avec résultat incertain, une vérification par le
responsable est nécessaire avant réimpression : revenir au portrait reste possible.
Aucun détail technique n'est présenté au visiteur ; les diagnostics vont dans
`kiosk.log` (à côté des scripts, exclu de Git).

Sans file configurée, l'aperçu et les fichiers restent disponibles ; une demande
d'impression aboutit à un message d'indisponibilité, sans impression. Les fichiers
des sessions restent sous `portraits/visiteurs/`, les démos sous `portraits/demo/`.
Le retour à l'accueil efface l'aperçu de l'écran, **pas les fichiers enregistrés**.
Prévoir leur suppression périodique selon l'usage de la borne.

### Logos et réglages

Tous les réglages se trouvent dans `config.py`, puis nécessitent un redémarrage :

| Réglage | Usage |
| --- | --- |
| `KIOSK_STARTUP_LOGO`, `KIOSK_HOME_LOGO` | Deux fichiers PNG indépendants, transparence et proportions conservées ; visuels distincts de remplacement si absents/illisibles. Aucun sélecteur au démarrage. |
| `KIOSK_SPLASH_SECONDS`, `KIOSK_TRANSITION_SECONDS` | Durée du lancement et apparition douce de l'accueil. |
| `KIOSK_FULLSCREEN`, `KIOSK_WINDOW_SIZE` | Mode et taille de développement par défaut ; les arguments CLI ont priorité. |
| `KIOSK_COLORS`, `KIOSK_FONT` | Palette et police ; utiliser une police installée sur le Pi. |
| `KIOSK_STABLE_SECONDS` | Durée de stabilité avant présentation de la caméra. |
| `KIOSK_SMOOTHING_SECONDS` | Constante de temps du lissage exponentiel ; zéro le désactive. |
| `KIOSK_CENTER_THRESHOLD` | Déplacement maximum du centre, en fraction de largeur/hauteur de l'image. |
| `KIOSK_SIZE_THRESHOLD` | Variation relative maximum de largeur/hauteur du visage. |
| `KIOSK_MIN_FACE_WIDTH`, `KIOSK_MIN_FACE_HEIGHT`, `KIOSK_FRAME_MARGIN` | Visibilité minimale et distance minimale aux bords, coordonnées normalisées 0–1. |
| `KIOSK_FRAME_TIMEOUT_SECONDS` | Âge maximum d'une capture exploitable ; aucune photo sur une ancienne détection. |
| `KIOSK_PREVIEW_SECONDS`, `KIOSK_COUNTDOWN_SECONDS`, `KIOSK_FLASH_SECONDS` | Délai pour se voir, compte à rebours (3 s par défaut) et flash. |
| `KIOSK_CHOICE_TIMEOUT_SECONDS` | Retour à l'accueil après inactivité dans le choix, le message Dessin ou une erreur d'impression. Jamais pendant un envoi. |
| `KIOSK_SUCCESS_TIMEOUT_SECONDS`, `KIOSK_DEPARTURE_SECONDS` | Retour après prise en charge et temps d'absence pour réarmer l'accueil. |
| `KIOSK_MIRROR` | Effet miroir indépendant pour la borne, appliqué aussi à la capture. |

Par défaut, les chemins des logos pointent vers `assets/startup-logo.png` et
`assets/home-logo.png`. Créer ce dossier et y déposer les PNG ou modifier les
chemins. Pour la stabilité, augmenter les seuils tolère davantage de mouvements ;
augmenter la durée oblige à garder la pose plus longtemps. Le calcul suit
l'enveloppe du visage, pas les paupières ou les lèvres : clignements et petites
expressions restent tolérés. Un ancrage empêche qu'une dérive lente paraisse stable.
Les temps utilisent une horloge monotone, indépendamment du nombre d'images.

Le module `kiosk_flow.py` contient les états et le point d'intégration futur
`request_robot_drawing()`. Ce dernier renvoie seulement le message d'indisponibilité.
La borne détecte jusqu'à trois visages, indépendamment du réglage mono-visage
de l'animation historique.

### Démonstration et vérifications

```bash
python kiosk.py --demo --windowed
python -m unittest discover -s tests -v
python tests/kiosk_smoke.py
```

Le mode **`--demo`** est explicitement marqué à l'écran. Il utilise une illustration
et des détections synthétiques ; il n'ouvre ni caméra ni modèle MediaPipe et ne
peut jamais appeler CUPS. L'action Impression est signalée comme une simulation,
pas comme une impression physique réussie. Les exports cartoon sont réellement
créés pour vérifier le parcours. Le contrôle graphique `kiosk_smoke.py` utilise
uniquement ce mode, teste le parcours et le double clic, et enregistre des captures
de sa propre fenêtre dans `portraits/demo/interface/` ; il requiert un bureau.

Les tests couvrent notamment les durées de stabilité, les petites expressions,
la dérive lente, les pertes d'image, les visages multiples, l'annulation du compte
à rebours, une capture unique, l'interdiction de réimprimer pendant l'envoi,
le réarmement après départ et l'interdiction matérielle du mode démo. Les tests
CUPS existants restent simulés.

Une caméra absente/débranchée produit un écran d'attente ou d'erreur et le processus
d'acquisition tente de rouvrir le périphérique. **Réessayer** relance le parcours
et, si nécessaire, le processus arrêté. Un appel caméra bloqué ne bloque pas
l'interface ; fermer puis relancer la borne si le backend ne se rétablit pas.
La fermeture demande l'arrêt et la libération de la caméra/du détecteur ; un
processus bloqué est terminé après un délai borné. Un envoi CUPS déjà engagé
se termine en arrière-plan, sans nouvel essai automatique.

Reste à valider sur le matériel : fluidité MediaPipe sur Pi 5 avec plusieurs
visages, seuils de stabilité selon distance/éclairage, comportement du tactile
et de la police, plein écran du bureau choisi, déconnexion/reconnexion USB,
pilote SELPHY, cadrage et rendu du vrai papier RP-108. Ne pas lancer les tests
matériels avec `--demo`.

## Exécution

Utiliser un environnement Python disposant de `mediapipe`, `opencv-python`
et `numpy`, avec une session graphique et une caméra accessible à OpenCV
(index 0). Le modèle `face_landmarker.task` doit rester à côté du script.

```bash
python3 face_landmarks_camera.py
```

Appuyer sur `q` pour quitter. Sous Linux, le programme utilise le backend
caméra natif d'OpenCV. Pour une caméra CSI, son intégration avec la pile caméra
du Raspberry Pi devra être vérifiée sur le matériel.

Les constantes sont regroupées dans `config.py` : caméra, détection, modèle,
calibration, lissage, couleurs et géométrie. Modifier ce fichier, puis relancer.
Les MAJUSCULES sont une convention Python ; les valeurs restent modifiables.
Le dessin est calibré pour 32 × 32 : changer la taille nécessite aussi de
revoir les positions et les dimensions du visage. Les indices anatomiques
sont liés au modèle MediaPipe et doivent normalement rester inchangés.

Les constantes `DEADZONE_*` de `config.py` règlent la stabilité des mouvements.
Une valeur de zéro désactive le filtre correspondant.

## Portrait cartoon — Canon SELPHY CP1500 / RP-108

Dans la fenêtre caméra, appuyer sur `p` lorsqu'un visage est détecté.
Le programme photographie le premier visage détecté, le recadre avec une marge,
puis applique l'effet cartoon existant avec une déformation centrale amusante.
La capture conserve l'effet miroir configuré, sans les points ni les diagnostics
affichés à l'écran. Sans visage détecté, aucune photo n'est enregistrée.

Chaque capture crée un dossier daté dans `portraits/`, à côté du script :

- `photo.png` : photo recadrée ;
- `cartoon.png` : résultat cartoon ;
- `tirage.png` : photo couleur portrait **1181 × 1748 pixels**, métadonnées 300 ppp ;
- `imprimer.html` : export autonome au format **100 × 148 mm**, sans titre sur la photo.

Une fenêtre d'aperçu s'ouvre avec le bouton explicite **Imprimer**. La capture
seule ne déclenche jamais d'impression. Fermer l'aperçu avant de reprendre une
photo. La génération utilise un thread ; l'aperçu utilise un processus séparé
et l'envoi CUPS un thread de ce processus : l'animation caméra reste active.

Le cartoon entier est centré sur fond blanc, sans étirement ni nouveau recadrage.
`PRINT_SAFETY_MARGIN_MM` dans `config.py` ajoute une marge de sécurité sur chaque
côté (4 mm par défaut), à ajuster après essai réel du pilote sans bordure.
Le recadrage initial conserve ses marges autour du visage ; les cheveux hors de
la capture ou de ce recadrage ne peuvent pas être reconstruits. Vérifier l'aperçu
et refaire la photo plus loin si nécessaire. L'agrandissement à 300 ppp prépare
le format de sortie, **sans créer de détails supplémentaires**. Aucun texte
n'est ajouté au tirage.

Avec `PRINTER_QUEUE = ""`, le bouton est désactivé : l'aperçu et les exports
fonctionnent sans imprimante, y compris sous Windows. Pour rouvrir un aperçu :

```bash
python portrait_preview.py /chemin/vers/portraits/portrait-DATE/tirage.png
```

L'export HTML peut s'ouvrir dans un navigateur pour enregistrer un PDF (100 ×
148 mm, marges nulles, sans en-têtes/pieds de page). Ce dialogue navigateur est
indépendant de l'envoi CUPS de la borne et de sa protection contre les doublons.

Cette première version utilise uniquement OpenCV : aucune IA générative,
aucune clé API, aucun coût par image et aucun envoi de photo sur Internet.
Les photos restent dans `portraits/` jusqu'à leur suppression manuelle ; ce dossier
est exclu de Git.

### Installer et configurer l'impression sur Raspberry Pi OS

La [documentation Canon](https://cam.start.canon/en/P001/manual/html/UG-07_Reference_0070.html)
indique 300 × 300 ppp et 100 × 148 mm après retrait des bandes du papier carte
postale (100 × 177 mm avant retrait). Garder les bandes pendant l'impression,
utiliser la cassette carte postale et le consommable RP-108 adaptés. Connecter
de préférence le Pi au port USB-C de la CP1500 avec un câble de données.

La [liste officielle Gutenprint 5.3.5](https://gimp-print.sourceforge.io/p_Supported_Printers.php)
inclut la CP1500, mais cela ne garantit pas sa présence dans les paquets de
votre version de Raspberry Pi OS. Vérifier le système et le pilote réellement
installés ; ne pas remplacer arbitrairement le modèle par une autre SELPHY.

```bash
cat /etc/os-release
uname -m
sudo apt update
apt-cache policy cups printer-driver-gutenprint
sudo apt install cups cups-client cups-filters printer-driver-gutenprint python3-tk
sudo systemctl enable --now cups
dpkg-query -W cups printer-driver-gutenprint
lpinfo -m | grep -i cp1500
lpinfo -v
```

Si la CP1500 n'apparaît pas dans `lpinfo -m`, le pilote disponible n'est pas
encore validé pour cette installation. Installer un paquet compatible fourni
pour votre distribution ou suivre les instructions de compilation de la
[version Gutenprint appropriée](https://sourceforge.net/projects/gimp-print/files/gutenprint-5.3/5.3.5/),
puis revérifier le modèle et son backend USB. Le projet n'installe ni ne compile
automatiquement un pilote. Ne pas créer une file brute pour contourner ce contrôle.

Depuis le bureau du Pi, ajouter l'imprimante via l'administration CUPS
`http://localhost:631` : choisir le périphérique USB réellement détecté et
le pilote CP1500 effectivement installé. Le compte administrateur peut nécessiter
le groupe `lpadmin` (puis une reconnexion). On peut aussi utiliser `lpadmin`
avec **l'URI exacte de `lpinfo -v` et l'identifiant exact de `lpinfo -m`**.

Une fois la file créée, remplacer `NOM_FILE` par son nom réel :

```bash
lpstat -p -d
lpstat -v NOM_FILE
lpoptions -p NOM_FILE -l
lpoptions -p NOM_FILE
```

Dans `config.py`, définir `PRINTER_QUEUE = "NOM_FILE"`. Dans `PRINTER_OPTIONS`,
copier les clés et valeurs internes présentes dans la sortie `lpoptions -l`,
sans les libellés après `/` ni l'astérisque du choix courant. Par exemple, une
ligne `Cle/Libelle: *ValeurAutre ValeurChoisie` correspond à
`PRINTER_OPTIONS = {"Cle": "ValeurChoisie"}`. Cet exemple illustre la syntaxe,
pas un nom de papier ou une option réelle de la CP1500.

Configurer ainsi le format carte postale correspondant au RP-108, la couleur
et les éventuels réglages de bordure/qualité exposés. Aucun nom `4x6`,
`Postcard` ou autre n'est supposé par le programme. Un dictionnaire vide utilise
les choix par défaut de la file : **les vérifier en couleur et au bon format**
avant d'ouvrir la borne au public. Les options explicites sont redécouvertes et
validées à chaque envoi ; une option inconnue est refusée.

L'envoi utilise `lp -d NOM_FILE -n 1 -o fit-to-page -o orientation-requested=3`,
puis les options configurées et le chemin absolu du PNG. Ces deux options
standard CUPS demandent l'ajustement sans découpe et l'orientation portrait ;
le pilote peut encore appliquer son propre agrandissement sans bordure.
Voir les [options CUPS](https://www.cups.org/doc/options.html) et
[lpoptions](https://www.cups.org/doc/man-lpoptions.html).

### État, erreurs et dépannage

- **Travail accepté par CUPS** signifie que `lp` a accepté l'envoi ; ce n'est
  pas la confirmation d'une photo physiquement sortie. Le reçu CUPS est affiché
  et conservé dans `tirage.cups-submission`.
- Le bouton est désactivé pendant l'envoi. Une création de fichier exclusive
  interdit les doubles clics et les envois concurrents du même portrait.
  Le verrou est conservé après toute tentative d'appel à `lp`, même en erreur
  ou en délai dépassé : le résultat peut être incertain. Aucun nouvel essai automatique.
- Absence de file configurée : mode aperçu/export. Fichier manquant, commande
  absente, file inexistante et option non exposée produisent un message d'erreur.
  Les erreurs avant l'appel à `lp` permettent de réessayer après correction.
- `lpstat -p NOM_FILE` vérifie l'état de la file ; `lpstat -W not-completed -o NOM_FILE`
  liste les travaux en attente. Vérifier aussi l'écran de la CP1500, le papier,
  le ruban, le câble et `journalctl -u cups`. Un travail peut être accepté alors
  que la file est suspendue ou l'imprimante débranchée.
- Si `lp`, `lpstat` ou `lpoptions` est absent, installer `cups-client`. Si l'aperçu
  échoue avec `No module named tkinter`, installer `python3-tk` pour l'interpréteur
  utilisé ; il faut une session graphique. Le PNG et le HTML restent exportés.
- Après vérification opérateur qu'aucun travail ne risque de sortir en double,
  supprimer uniquement le fichier `tirage.cups-submission` du portrait concerné
  pour autoriser une nouvelle tentative, puis rouvrir l'aperçu. Le verrou est
  local au portrait : il ne protège pas des impressions lancées hors de la borne.

À valider sur le Pi et la CP1500 physiques : disponibilité du pilote/backend
USB, choix exact du média et de la couleur, orientation, dimensions après retrait
des bandes, marges/agrandissement sans bordure, rendu couleur, fluidité de la
caméra et absence de second travail après un double clic. Les tests automatisés
simulent CUPS et ne lancent aucune impression réelle.

## Vérification sans caméra

```bash
python3 -m unittest discover -s tests -v
```

L'exécution réelle sur Raspberry Pi 5 reste à valider sur la machine cible.

## Installation et SSH sur Raspberry Pi

On flashe le système sur la carte SD, puis on copie et installe le projet Python.
Si un système adapté est déjà installé, conserver la carte et passer à SSH.

### 1. Préparer le système

Pour cette procédure, choisir **Raspberry Pi OS Bookworm avec bureau, 64 bits**
(Python 3.11), idéalement sur Pi 5. Dans Raspberry Pi Imager, chercher Bookworm
parmi les images anciennes/Legacy ou charger une image officielle Bookworm.
Le fichier `requirements-raspberry-pi.txt` utilise MediaPipe 0.10.18, disponible
en ARM64 pour Python 3.9 à 3.12. Python 3.13 ne convient pas à ces dépendances.
Voir les [paquets publiés sur PyPI](https://pypi.org/project/mediapipe/0.10.18/).

Dans Imager, sélectionner le Pi, le système et la carte SD. Personnaliser le
nom d'hôte (`robotpi` dans les exemples), le compte (`hachi`), le mot de passe,
le Wi-Fi et activer SSH (mot de passe ou clé). L'écriture efface la carte choisie.
Insérer la carte et démarrer le Pi sur le même réseau que le PC.
Voir le [guide officiel d'installation](https://www.raspberrypi.com/documentation/computers/getting-started.html).

### 2. Connexion depuis Windows

Dans PowerShell, remplacer le compte et le nom d'hôte par ceux configurés :

```powershell
ssh hachi@robotpi.local
```

Vérifier l'identité du Pi avant d'accepter sa clé à la première connexion.
Le mot de passe ne s'affiche pas pendant la saisie. Si `.local` échoue, utiliser
l'adresse IP visible dans la liste des appareils de la box :
`ssh hachi@192.168.1.42` (exemple). Sur un Pi déjà installé, activer SSH depuis
un terminal local avec `sudo raspi-config`, dans les options d'interface.
Voir la [documentation SSH](https://www.raspberrypi.com/documentation/computers/remote-access.html).

### 3. Copier le projet

Dans le terminal SSH :

```bash
mkdir -p ~/robot-face
exit
```

Dans PowerShell, depuis le dossier du projet :

```powershell
scp .\face_landmarks_camera.py .\portrait_cartoon.py .\portrait_preview.py .\portrait_printing.py .\config.py .\requirements-raspberry-pi.txt .\face_landmarker.task .\README.md hachi@robotpi.local:~/robot-face/
scp .\kiosk.py .\kiosk_camera.py .\kiosk_flow.py .\requirements-kiosk.txt hachi@robotpi.local:~/robot-face/
scp -r .\tests hachi@robotpi.local:~/robot-face/
ssh hachi@robotpi.local
```

Si le modèle manque sur le PC, enlever `face_landmarker.task` de la commande :
le programme le téléchargera au premier lancement, avec une connexion Internet.

### 4. Installer les dépendances via SSH

```bash
uname -m
python3 --version
```

Vérifier `aarch64` et Python 3.11 pour Bookworm. Si Python est en version 3.13,
utiliser Bookworm ou installer un interpréteur 3.11 dans un environnement
séparé avant de poursuivre.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip libgl1 libglib2.0-0 libegl1 libgles2
cd ~/robot-face
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-raspberry-pi.txt
python -m pip check
python -m unittest discover -s tests -v
```

`opencv-contrib-python` fournit `cv2` et satisfait MediaPipe. Ne pas ajouter
`opencv-python` ou une variante headless au même environnement : ces paquets
partagent `cv2`, et le programme nécessite un affichage graphique.

### 5. Lancer depuis le bureau du Pi

Brancher une webcam USB pour le premier essai. Ouvrir un terminal sur le bureau
du Pi, via un écran HDMI ou un bureau distant, puis exécuter :

```bash
cd ~/robot-face
source .venv/bin/activate
python face_landmarks_camera.py
```

Appuyer sur `q` dans la fenêtre pour quitter. SSH seul ne fournit pas de bureau
pour `cv2.imshow`. Pour utiliser le bureau à distance, consulter
[Raspberry Pi Connect ou VNC](https://www.raspberrypi.com/documentation/computers/remote-access.html).
Définir `DISPLAY=:0` arbitrairement ne garantit pas l'accès à la session graphique.

Si la caméra ne s'ouvre pas, vérifier `ls /dev/video*` et ajuster `CAMERA_INDEX`
dans `config.py`. Une caméra CSI peut demander une intégration Picamera2/libcamera ;
son accès par `cv2.VideoCapture` n'est pas garanti par ce projet.

Pour modifier les réglages sur le Pi : `nano ~/robot-face/config.py`.
Pour recopier une modification depuis PowerShell :

```powershell
scp .\config.py hachi@robotpi.local:~/robot-face/
```

Relancer l'application après chaque modification.
