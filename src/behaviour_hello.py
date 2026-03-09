import cv2
import time
from gtts import gTTS
import subprocess

def falar(texto):
    gTTS(text=texto, lang='pt').save("temp_audio.mp3")
    subprocess.Popen(["start", "temp_audio.mp3"], shell=True)

def main():
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Erro: webcam não abriu.")
        return

    face_detected = False # cara vista antes
    last_seen = 0 # ultima vez visto
    delay = 1.0  # segundos sem cara para considerar desaparecido

    while True:
        ret, frame = cap.read()

        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) # muda de RBG para preto e branco.
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(70, 70))
        has_face = len(faces) > 0
        now = time.time()
        
        if has_face:
            last_seen = now
        
            if not face_detected:
                falar("Olá") # função do tts
                face_detected = True
        
        else:
            if now - last_seen > delay:
                face_detected = False
        
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imshow("Face Detection", frame) 
        
        if cv2.waitKey(1) == ord('s'): 
            break
    
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()