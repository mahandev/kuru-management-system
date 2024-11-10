import qrcode
from PIL import Image
from io import BytesIO
import base64


def create_qr_code_with_logo(url, logo_path, qr_size=290, logo_size=130):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="rgb(213,68,39)", back_color="white")
    qr_img = qr_img.convert("RGBA")

    # Load the logo
    logo = Image.open(logo_path)
    logo = logo.convert("RGBA")
    logo = logo.resize((logo_size, logo_size))

    # Position of the logo
    x = (qr_img.width - logo.width) // 2
    y = (qr_img.height - logo.height) // 2

    # Paste the logo onto the QR code image with transparency handling
    qr_img.paste(logo, (x, y), logo)

    return qr_img


def generate_qr_code_as_base64(url, logo_path):
    qr_img = create_qr_code_with_logo(url, logo_path)

    # Save QR code to in-memory image buffer
    img_io = BytesIO()
    qr_img.save(img_io, format="PNG")
    img_io.seek(0)

    # Convert image to base64 encoding
    return base64.b64encode(img_io.getvalue()).decode("utf-8")
