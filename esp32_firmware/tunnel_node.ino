/*
 * ESP32 BLE + LoRa Bridge Firmware
 * - Exposes BLE GATT server for Android app
 * - Relays queries over LoRa to surface gateway
 * - Returns cloud response back to app via BLE notification
 *
 * Libraries needed (install via Arduino Library Manager):
 *   - "LoRa" by Sandeep Mistry
 *   - "ESP32 BLE Arduino" (built-in with ESP32 board package)
 */

#include <SPI.h>
#include <LoRa.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// LoRa pins (adjust to your wiring)
#define LORA_SCK  5
#define LORA_MISO 19
#define LORA_MOSI 27
#define LORA_SS   18
#define LORA_RST  14
#define LORA_DIO0 26

// BLE UUIDs — must match App.tsx constants
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define QUERY_CHAR_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define RESPONSE_CHAR_UUID  "beb5483e-36e1-4688-b7f5-ea07361b26a9"

BLECharacteristic *pResponseChar;
bool deviceConnected = false;

// BLE Server callbacks
class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer *s)    { deviceConnected = true;  Serial.println("App connected"); }
  void onDisconnect(BLEServer *s) { deviceConnected = false; s->startAdvertising(); }
};

// Query characteristic write callback
class QueryCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic *pChar) {
    String query = pChar->getValue().c_str();
    Serial.println("Query from app: " + query);

    // Forward over LoRa
    LoRa.beginPacket();
    LoRa.print(query);
    LoRa.endPacket();

    // Wait up to 8s for LoRa response
    String response = "No response from surface gateway.";
    unsigned long t = millis();
    while (millis() - t < 8000) {
      if (LoRa.parsePacket()) {
        response = "";
        while (LoRa.available()) response += (char)LoRa.read();
        break;
      }
    }

    Serial.println("Response: " + response);

    // Notify app via BLE
    if (deviceConnected) {
      pResponseChar->setValue(response.c_str());
      pResponseChar->notify();
    }
  }
};

void setup() {
  Serial.begin(115200);

  // Init LoRa
  SPI.begin(LORA_SCK, LORA_MISO, LORA_MOSI, LORA_SS);
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(868E6)) {
    Serial.println("LoRa init failed!");
    while (1);
  }
  Serial.println("LoRa ready.");

  // Init BLE
  BLEDevice::init("Metro_Tunnel_Node");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new ServerCallbacks());

  BLEService *pService = pServer->createService(SERVICE_UUID);

  // Query characteristic (WRITE)
  BLECharacteristic *pQueryChar = pService->createCharacteristic(
    QUERY_CHAR_UUID,
    BLECharacteristic::PROPERTY_WRITE
  );
  pQueryChar->setCallbacks(new QueryCallbacks());

  // Response characteristic (NOTIFY)
  pResponseChar = pService->createCharacteristic(
    RESPONSE_CHAR_UUID,
    BLECharacteristic::PROPERTY_NOTIFY
  );
  pResponseChar->addDescriptor(new BLE2902());

  pService->start();
  BLEDevice::startAdvertising();
  Serial.println("BLE advertising as 'Metro_Tunnel_Node'");
}

void loop() {
  // Nothing needed — BLE callbacks handle everything
  delay(10);
}
