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
scp .\face_landmarks_camera.py .\config.py .\requirements-raspberry-pi.txt .\face_landmarker.task .\README.md hachi@robotpi.local:~/robot-face/
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
