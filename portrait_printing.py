"""Envoi CUPS explicite, options decouvertes, protection persistante par portrait."""

import os
from pathlib import Path
import re
import subprocess


class PrintError(RuntimeError):
    pass


def run_cups(args, timeout):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                env={**os.environ, "LC_ALL": "C"})
    except FileNotFoundError as exc:
        raise PrintError(f"Commande CUPS absente : {args[0]}.") from exc
    except subprocess.TimeoutExpired as exc:
        raise PrintError("Delai CUPS depasse. Verifier la file avant toute nouvelle tentative.") from exc
    except OSError as exc:
        raise PrintError(f"Impossible de lancer CUPS : {exc}") from exc
    if result.returncode:
        raise PrintError(f"Echec {args[0]} : {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def discover_options(queue, timeout=20):
    if not queue:
        raise PrintError("Aucune imprimante configuree : mode apercu/export.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", queue):
        raise PrintError("Nom de file CUPS invalide (sans instance ni espace).")
    # lpstat echoue si la destination n'existe pas ou si CUPS est inaccessible.
    run_cups(["lpstat", "-p", queue], timeout)
    raw = run_cups(["lpoptions", "-p", queue, "-l"], timeout)
    choices = {}
    for line in raw.splitlines():
        if ":" in line:
            name, values = line.split(":", 1)
            choices[name.split("/", 1)[0]] = {v.lstrip("*") for v in values.split()}
    return choices


def submit_print(image_path, queue, options, timeout=20):
    image = Path(image_path).resolve()
    if not image.is_file():
        raise PrintError(f"Fichier manquant : {image}")
    marker = image.with_suffix(".cups-submission")
    if marker.exists():
        raise PrintError("Envoi deja tente pour ce portrait. Consulter CUPS avant de reimprimer.")
    available = discover_options(queue, timeout)
    args = ["lp", "-d", queue, "-n", "1", "-o", "fit-to-page", "-o", "orientation-requested=3"]
    for key, value in options.items():
        if key not in available or str(value) not in available[key]:
            raise PrintError(f"Option non exposee par la file : {key}={value}. Utiliser lpoptions -p {queue} -l.")
        args.extend(["-o", f"{key}={value}"])
    args.append(str(image))
    # Creation exclusive : protege aussi contre deux fenetres/processus simultanes.
    try:
        with marker.open("x", encoding="utf-8") as stream:
            stream.write("Envoi en cours ou resultat inconnu. Verifier CUPS.\n")
    except FileExistsError as exc:
        raise PrintError("Envoi deja tente pour ce portrait.") from exc
    receipt = run_cups(args, timeout)
    marker.write_text(receipt + "\n", encoding="utf-8")
    return "Travail accepte par CUPS (impression physique non confirmee).\n" + receipt
