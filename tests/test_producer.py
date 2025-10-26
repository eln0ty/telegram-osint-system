from code.producer import TelegramProducer


def test_message_key_stable() -> None:
    assert TelegramProducer._message_key(123, 456) == TelegramProducer._message_key(123, 456)
    assert TelegramProducer._message_key(123, 456) != TelegramProducer._message_key(124, 456)
