#include <Arduino.h>
#include <PxMatrix.h>
#include <Adafruit_GFX.h>

#define P_LAT D9
#define P_OE  D10
#define P_A   A0
#define P_B   A1
#define P_C   A2
#define P_D   A3
#define P_E   A4

PxMATRIX display(64, 64, P_LAT, P_OE, P_A, P_B, P_C, P_D, P_E);
HardwareTimer* displayTimer = nullptr;

struct FaceData {
  int leftX;
  int leftY;
  int rightX;
  int rightY;
  int mouthOpening;
};

FaceData face = {8, 11, 23, 11, 0};
char lineBuffer[64];
size_t lineLength = 0;

void refreshDisplay() { display.display(70); }

void startDisplayTimer() {
  displayTimer = new HardwareTimer(TIM1);
  displayTimer->setOverflow(1000, MICROSEC_FORMAT);
  displayTimer->attachInterrupt(refreshDisplay);
  displayTimer->resume();
}

int clampLogicalPixel(int value) { return constrain(value, 0, 31); }
int toPhysicalPixel(int logicalPixel) { return logicalPixel * 2; }

bool parseFaceLine(const char* line, FaceData& parsed) {
  int xg, yg, xd, yd, mouth;
  char extra;
  int count = sscanf(line, "%d,%d,%d,%d,%d%c", &xg, &yg, &xd, &yd, &mouth, &extra);
  if (count != 5) return false;
  parsed.leftX = clampLogicalPixel(xg);
  parsed.leftY = clampLogicalPixel(yg);
  parsed.rightX = clampLogicalPixel(xd);
  parsed.rightY = clampLogicalPixel(yd);
  parsed.mouthOpening = constrain(mouth, 0, 12);
  return true;
}

void readSerialLines() {
  while (Serial.available() > 0) {
    char character = static_cast<char>(Serial.read());
    if (character == '\n') {
      lineBuffer[lineLength] = '\0';
      FaceData parsed;
      if (parseFaceLine(lineBuffer, parsed)) face = parsed;
      lineLength = 0;
    } else if (character != '\r') {
      if (lineLength < sizeof(lineBuffer) - 1) lineBuffer[lineLength++] = character;
      else lineLength = 0;
    }
  }
}

void drawFace(const FaceData& currentFace) {
  display.clearDisplay();
  const uint16_t white = display.color565(255, 255, 255);
  const uint16_t red = display.color565(255, 0, 0);
  display.drawCircle(toPhysicalPixel(currentFace.leftX), toPhysicalPixel(currentFace.leftY), 5, white);
  display.drawCircle(toPhysicalPixel(currentFace.rightX), toPhysicalPixel(currentFace.rightY), 5, white);
  constexpr int mouthX = 16;
  constexpr int mouthWidth = 32;
  constexpr int mouthBottom = 62;
  if (currentFace.mouthOpening == 0) {
    display.drawLine(mouthX, mouthBottom, mouthX + mouthWidth, mouthBottom, red);
  } else {
    int mouthY = mouthBottom - currentFace.mouthOpening * 2;
    display.fillRect(mouthX, mouthY, mouthWidth, currentFace.mouthOpening * 2, red);
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  display.begin(32);
  display.setBrightness(80);
  display.clearDisplay();
  startDisplayTimer();
}

void loop() {
  readSerialLines();
  drawFace(face);
  delay(10);
}
