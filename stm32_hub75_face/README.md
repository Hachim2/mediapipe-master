# Visage MediaPipe vers matrice HUB75 STM32

## Fichiers

- `hub75_face.ino` : sketch pour la Nucleo-F401RE.
- `platformio.ini` : configuration PlatformIO pour la Nucleo-F401RE.
- `src/main.cpp` : copie du sketch compilee par PlatformIO.
- `test_hub75_serial.py` : test sans camera.
- `face_landmarks_camera.py` : copie conseillee du script MediaPipe existant, apres ajout de la sortie serie indiquee ci-dessous.

## 1. Installer le materiel logiciel

Dans Arduino IDE :

1. Installer le support de cartes STM32 par STM32duino.
2. Installer les bibliotheques `PxMatrix` et `Adafruit GFX Library`.
3. Ouvrir `hub75_face.ino`.
4. Selectionner la carte Nucleo-F401RE et le port COM du ST-LINK.
5. Televerser le sketch.

Le port serie utilise 115200 bauds.

## Flash avec PlatformIO

1. Ouvrir le dossier `stm32_hub75_face` dans VS Code, pas seulement le fichier `.ino`.
2. Attendre l'installation automatique de la plateforme STM32 et des bibliotheques.
3. Brancher la Nucleo avec le connecteur USB ST-LINK.
4. Cliquer sur l'icone PlatformIO, puis `Project Tasks` -> `nucleo_f401re` -> `Upload`.

Le fichier `platformio.ini` utilise `upload_protocol = stlink` et le port serie a 115200 bauds. Le moniteur se lance avec `Monitor` dans PlatformIO.

Si PlatformIO n'est pas installe dans VS Code, installer l'extension `PlatformIO IDE`, redemarrer VS Code, puis ouvrir ce dossier comme projet.

## 2. Cablage

- R1=D2, G1=D3, B1=D4
- R2=D5, G2=D6, B2=D7
- A=A0, B=A1, C=A2, D=A3, E=A4
- CLK=D8, LAT=D9, OE=D10

La matrice doit avoir une alimentation 5 V separee et suffisamment puissante. Relier la masse de cette alimentation a GND de la Nucleo. Ne pas alimenter la matrice depuis la Nucleo.

## 3. Tester la liaison sans MediaPipe

Depuis PowerShell :

```powershell
cd C:\Users\Hachi\OneDrive\Desktop\stm32_hub75_face
py -m pip install pyserial
py .\test_hub75_serial.py COM5
```

Remplacer `COM5` par le port affiche dans Arduino IDE. Fermer le moniteur serie Arduino avant de lancer Python, car un seul programme peut ouvrir le port COM.

## 4. Lancer MediaPipe

Installer les dependances si necessaire :

```powershell
cd C:\Users\Hachi\OneDrive\Desktop
py -m pip install mediapipe opencv-python numpy pyserial
```

Dans `face_landmarks_camera.py`, regler :

```python
SERIAL_PORT = "COM5"
```

Puis lancer :

```powershell
cd C:\Users\Hachi\OneDrive\Desktop
py .\face_landmarks_camera.py
```

Appuyer sur `q` pour quitter.

### Regler les zones mortes

Dans `face_landmarks_camera.py`, les constantes `DEADZONE_*` reglent les
mouvements minimums qui font changer l'animation :

- `DEADZONE_PUPIL = 0.30` : deplacement horizontal et vertical du regard.
- `DEADZONE_EYE_OPEN = 0.08` : ouverture de chaque paupiere, sur une echelle de 0 a 1.
- `DEADZONE_MOUTH_OPEN = 0.45` : ouverture de la bouche.
- `DEADZONE_MOUTH_WIDTH = 0.50` : largeur de la bouche.
- `DEADZONE_SMILE = 0.20` : courbure du sourire.

Hors paupieres, les seuils sont exprimes en LEDs logiques 32x32. Augmenter
un seuil stabilise davantage le visage ; le diminuer rend le mouvement plus
sensible. Mettre un seuil a `0` desactive sa zone morte. Relancer le script
apres modification.

La reference reste la derniere mesure acceptee : les petits tremblements sont
ignores, mais un mouvement lent et continu finit par depasser le seuil.
Les mouvements acceptes gardent le lissage existant. La bouche est filtree
avant son seuil d'ouverture pour eviter une alternance ferme/ouvert.
Le regard et l'ouverture de la bouche sont aussi filtres dans les donnees
envoyees au STM32. Les paupieres, la largeur et le sourire concernent l'apercu
sur l'ordinateur, car le protocole actuel ne transmet pas ces parametres.

Le protocole envoye est :

```text
XG,YG,XD,YD,OB\n
```

Exemple : `8,11,23,11,4`.

Toutes les valeurs sont en coordonnees logiques 32x32. Le firmware les
agrandit automatiquement x2 pour l'affichage sur la matrice physique 64x64.
`XG,YG` et `XD,YD` definissent les deux yeux ; `OB` est l'ouverture de bouche.
