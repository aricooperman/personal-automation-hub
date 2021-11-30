import os
import tempfile
from typing import IO


def get_image_full_text(file_name: str, img_file_like: IO) -> str:
    if file_name is None or len(file_name.strip()) == 0:
        file_name = "tmp.file"

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file_name = f"{tmpdir}/{file_name}"
        with open(tmp_file_name, mode="wb") as img_file:
            img_file.write(img_file_like.read())

        ocr_cmd = f"tesseract -l eng '{tmp_file_name}' -"
        out_pipe = os.popen(ocr_cmd, mode="r")
        img_text = ""
        lines = out_pipe.readlines()
        for line in lines:
            img_text += '> ' + line.replace('>', r'\>')

        os.remove(tmp_file_name)
        return img_text
