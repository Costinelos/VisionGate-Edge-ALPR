import cv2
import logging
from datetime import datetime
from ultralytics import YOLO

logger = logging.getLogger(__name__)


class ImageProcessor:
    def __init__(self, model_path="models/best.pt"):
        self.model = YOLO(model_path)

    def process_and_crop(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            return []

        results = self.model(img, conf=0.5, verbose=False)
        crops = []

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])


                width = x2 - x1
                x1_nou = x1 + int(width * 0.12)
                x2_nou = x2 - int(width * 0.02)


                if x1_nou >= x2_nou:
                    x1_nou, x2_nou = x1, x2

                crop = img[y1:y2, x1_nou:x2_nou]
                # -----------------------------------------

                if crop.size > 0:
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)

                    crop_path = f"captures/crop_{datetime.now().strftime('%H%M%S')}.jpg"
                    cv2.imwrite(crop_path, enhanced)
                    crops.append({"image": enhanced, "path": crop_path})

        return crops