# Visage animé sur Raspberry Pi 5

Le programme suit les yeux et la bouche avec MediaPipe et affiche la caméra
ainsi que le visage animé dans une fenêtre OpenCV. Le rendu à points lumineux
reste un effet visuel à l'écran. Aucune donnée n'est envoyée à un microcontrôleur
ou à une matrice LED physique.

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
