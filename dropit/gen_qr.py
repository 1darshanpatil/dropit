import qrcode

def create_qr_in_terminal(text):
    qr = qrcode.QRCode(
            version = 1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
    qr.add_data(text)
    qr.make(fit=True)
    qr.print_ascii(invert= True)

if __name__ == "__main__":
    create_qr_in_terminal(input("Enter your text or URL: "))
