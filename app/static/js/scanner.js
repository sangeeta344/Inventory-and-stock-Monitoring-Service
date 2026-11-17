/**
 * Smart Supermarket - Mobile & Webcam Barcode Scanner Engine
 * Integrates HTML5 Camera Video Stream with ZXing / Html5Qrcode
 */

class BarcodeScannerController {
    constructor(elementId, onScanSuccess) {
        this.elementId = elementId;
        this.onScanSuccess = onScanSuccess;
        this.html5QrCode = null;
        this.isScanning = false;
        this.lastScannedCode = null;
        this.lastScanTime = 0;
        this.scanCooldownMs = 1500; // prevent immediate re-triggering of the same barcode
        this.audioCtx = null;
    }

    // Audio synthesizer beep for instant audio scan feedback
    playBeep() {
        try {
            if (!this.audioCtx) {
                this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
            const osc = this.audioCtx.createOscillator();
            const gain = this.audioCtx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(1200, this.audioCtx.currentTime); // 1200Hz pleasant beep
            gain.gain.setValueAtTime(0.2, this.audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, this.audioCtx.currentTime + 0.15);
            osc.connect(gain);
            gain.connect(this.audioCtx.destination);
            osc.start();
            osc.stop(this.audioCtx.currentTime + 0.15);
        } catch (e) {
            console.log("Audio feedback error:", e);
        }
    }

    startScanning(cameraFacingMode = "environment") {
        if (typeof Html5Qrcode === "undefined") {
            console.error("Html5Qrcode library is not loaded.");
            alert("Camera scanner library is loading, please try again in a moment.");
            return;
        }

        const scannerElement = document.getElementById(this.elementId);
        if (!scannerElement) return;

        if (this.isScanning) {
            this.stopScanning();
        }

        this.html5QrCode = new Html5Qrcode(this.elementId);
        const config = {
            fps: 15,
            qrbox: { width: 260, height: 160 },
            aspectRatio: 1.777778,
            formatsToSupport: [
                Html5QrcodeSupportedFormats.EAN_13,
                Html5QrcodeSupportedFormats.EAN_8,
                Html5QrcodeSupportedFormats.UPC_A,
                Html5QrcodeSupportedFormats.UPC_E,
                Html5QrcodeSupportedFormats.CODE_128,
                Html5QrcodeSupportedFormats.CODE_39,
                Html5QrcodeSupportedFormats.QR_CODE
            ]
        };

        const qrCodeSuccessCallback = (decodedText, decodedResult) => {
            const now = Date.now();
            if (this.lastScannedCode === decodedText && (now - this.lastScanTime) < this.scanCooldownMs) {
                return; // Cooldown for same barcode
            }

            this.lastScannedCode = decodedText;
            this.lastScanTime = now;
            this.playBeep();

            if (this.onScanSuccess) {
                this.onScanSuccess(decodedText);
            }
        };

        // Prefer back camera for smartphones ('environment')
        this.html5QrCode.start(
            { facingMode: cameraFacingMode },
            config,
            qrCodeSuccessCallback,
            (errorMessage) => {
                // frame did not contain barcode, ignore
            }
        ).then(() => {
            this.isScanning = true;
            const statusEl = document.getElementById('scanner-status-text');
            if (statusEl) statusEl.innerText = "Camera active. Align barcode inside frame.";
        }).catch((err) => {
            console.error("Unable to start camera scanner:", err);
            this.isScanning = false;
            let msg = "Could not access camera. ";
            if (window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
                msg += "Mobile browsers require HTTPS or localhost to grant camera permissions.";
            } else {
                msg += "Please ensure camera permissions are allowed in your browser settings.";
            }
            alert(msg);
        });
    }

    stopScanning() {
        if (this.html5QrCode && this.isScanning) {
            this.html5QrCode.stop().then(() => {
                this.isScanning = false;
                this.html5QrCode.clear();
            }).catch(err => {
                console.error("Failed to stop scanner:", err);
            });
        }
    }

    toggle() {
        if (this.isScanning) {
            this.stopScanning();
        } else {
            this.startScanning();
        }
    }
}

window.BarcodeScannerController = BarcodeScannerController;
