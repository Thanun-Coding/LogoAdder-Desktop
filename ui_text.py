KHMER_DIGITS = str.maketrans("0123456789", "០១២៣៤៥៦៧៨៩")
ASCII_DIGITS = str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")


def to_khmer_digits(value):
    return str(value).translate(KHMER_DIGITS)


def from_khmer_digits(value):
    return str(value).translate(ASCII_DIGITS)
