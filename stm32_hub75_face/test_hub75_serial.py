import argparse
import time

import serial


def main():
    parser = argparse.ArgumentParser(description="Test du protocole serie HUB75")
    parser.add_argument("port", help="Port COM du ST-LINK, par exemple COM5")
    args = parser.parse_args()
    with serial.Serial(args.port, 115200, timeout=1) as connection:
        print(f"Envoi vers {args.port}. Ctrl+C pour arreter.")
        while True:
            connection.write(b"8,11,23,11,4\n")
            time.sleep(0.1)


if __name__ == "__main__":
    main()
