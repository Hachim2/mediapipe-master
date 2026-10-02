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

Les constantes `DEADZONE_*` du script règlent la stabilité des mouvements.
Une valeur de zéro désactive le filtre correspondant.

## Vérification sans caméra

```bash
python3 -m unittest discover -s tests -v
```

L'exécution réelle sur Raspberry Pi 5 reste à valider sur la machine cible.
