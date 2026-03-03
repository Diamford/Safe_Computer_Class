// SCC_rfid_scanner.ino
// ESP32-C3 + RC522 + SHA-256
// Протокол по Serial:
//   ПК -> ESP:  "HELLO_SCC\n"
//   ESP -> ПК:  "SCC_RFID_V1_OK\n"
//   ESP -> ПК:  "CARD_HASH:<HEX_SHA256(UID||SALT)>\n"

#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>
#include "mbedtls/sha256.h"

// ===================== Пины (подстройте под свою плату) =====================
// Для ESP32-C3 DevKit проверьте реальную распиновку и при необходимости
// измените значения ниже.

#define RFID_SS_PIN   7    // SDA / SS RC522
#define RFID_RST_PIN  3    // RST RC522
#define SPI_SCK_PIN   4
#define SPI_MISO_PIN  5
#define SPI_MOSI_PIN  6

// ===================== Протокол по Serial =====================

const char *HANDSHAKE_REQUEST  = "HELLO_SCC";
const char *HANDSHAKE_RESPONSE = "SCC_RFID_V1_OK";
const char *PREFIX_CARD_HASH   = "CARD_HASH:";

// ===================== Соль (salt) для SHA-256 =====================
// В боевом устройстве ЗАМЕНИТЕ на свои случайные байты и не публикуйте их.

const uint8_t SALT[] = {
  0xA3, 0x5F, 0x91, 0x2C,
  0x47, 0xD8, 0x6E, 0x10,
  0xB4, 0x29, 0x7A, 0xCC,
  0x03, 0x8D, 0xE1, 0x5B
};

const size_t SALT_LEN = sizeof(SALT);

// ===================== RFID =====================

MFRC522 mfrc522(RFID_SS_PIN, RFID_RST_PIN);

// Состояния протокола
enum State {
  WAIT_HANDSHAKE,
  WAIT_CARD
};

State currentState = WAIT_HANDSHAKE;

// Буфер для входящей строки по Serial
String serialLine;

// ===================== Вспомогательные функции =====================

// SHA-256(data) -> outHash[32]
void computeSHA256(const uint8_t *data, size_t len, uint8_t outHash[32]) {
  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);

  // 0 = SHA-256, 1 = SHA-224
  mbedtls_sha256_starts_ret(&ctx, 0);
  mbedtls_sha256_update_ret(&ctx, data, len);
  mbedtls_sha256_finish_ret(&ctx, outHash);

  mbedtls_sha256_free(&ctx);
}

// Преобразовать байты в HEX-строку (верхний регистр)
String bytesToHex(const uint8_t *data, size_t len) {
  const char hexChars[] = "0123456789ABCDEF";
  String out;
  out.reserve(len * 2);
  for (size_t i = 0; i < len; ++i) {
    uint8_t b = data[i];
    out += hexChars[b >> 4];
    out += hexChars[b & 0x0F];
  }
  return out;
}

// Чтение строковых команд из Serial до '\n'
void handleSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') {
      // игнорируем CR
      continue;
    } else if (c == '\n') {
      // получена полная строка
      String line = serialLine;
      serialLine = "";

      line.trim();
      if (line.length() == 0) {
        return;
      }

      if (currentState == WAIT_HANDSHAKE) {
        if (line.equals(HANDSHAKE_REQUEST)) {
          // Отвечаем, что устройство готово
          Serial.println(HANDSHAKE_RESPONSE);
          currentState = WAIT_CARD;
        } else {
          // Неизвестная команда
          Serial.println("ERR:UNKNOWN_CMD");
        }
      } else if (currentState == WAIT_CARD) {
        // В этом состоянии можно обрабатывать дополнительные команды (например RESET)
        if (line.equals("RESET")) {
          currentState = WAIT_HANDSHAKE;
          Serial.println("OK:RESET");
        }
      }
    } else {
      // накапливаем в буфер строки
      if (serialLine.length() < 200) {  // простая защита от переполнения
        serialLine += c;
      } else {
        // Слишком длинная строка — сброс буфера
        serialLine = "";
      }
    }
  }
}

// Обработка RFID-карты в состоянии WAIT_CARD
void handleRFID() {
  if (currentState != WAIT_CARD) return;

  // Проверяем наличие новой карты
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // UID карты
  uint8_t uidBytes[10]; // обычно 4 или 7 байт, но возьмём с запасом
  uint8_t uidLen = mfrc522.uid.size;
  if (uidLen > sizeof(uidBytes)) {
    uidLen = sizeof(uidBytes);
  }
  memcpy(uidBytes, mfrc522.uid.uidByte, uidLen);

  // Собираем данные: UID || SALT
  const size_t totalLen = uidLen + SALT_LEN;
  uint8_t *data = (uint8_t *)malloc(totalLen);
  if (!data) {
    Serial.println("ERR:MEMORY");
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    currentState = WAIT_HANDSHAKE;
    return;
  }

  memcpy(data, uidBytes, uidLen);
  memcpy(data + uidLen, SALT, SALT_LEN);

  // SHA-256(UID || SALT)
  uint8_t hash[32];
  computeSHA256(data, totalLen, hash);

  free(data);

  // Переводим в HEX
  String hashHex = bytesToHex(hash, sizeof(hash));

  // Отправляем на ПК
  Serial.print(PREFIX_CARD_HASH);
  Serial.println(hashHex);

  // Завершение работы с картой
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();

  // Возвращаемся к ожиданию нового рукопожатия
  currentState = WAIT_HANDSHAKE;
}

// ===================== Arduino setup/loop =====================

void setup() {
  // Serial
  Serial.begin(115200);
  while (!Serial) {
    // ждём инициализации USB-Serial
    delay(10);
  }

  // Инициализация SPI для ESP32-C3
  SPI.begin(SPI_SCK_PIN, SPI_MISO_PIN, SPI_MOSI_PIN, RFID_SS_PIN);

  // Инициализация RC522
  mfrc522.PCD_Init();
  delay(50);

  Serial.println("SCC RFID device booted");
  Serial.println("State: WAIT_HANDSHAKE");
}

void loop() {
  // 1. Обработка входящих команд по Serial
  handleSerialInput();

  // 2. В состоянии WAIT_CARD — ждём и читаем карту
  handleRFID();
}

