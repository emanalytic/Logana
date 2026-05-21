from logana.utils.ringBuffer import RingBuffer


def test_ringBufferEvictsOldest():
    buf = RingBuffer(3)
    for v in [1, 2, 3, 4]:
        buf.push(v)
    assert buf.getValues() == [2, 3, 4]


def test_ringBufferMedianAndMad():
    buf = RingBuffer(5)
    for v in [1, 2, 3, 4, 100]:
        buf.push(v)
    assert buf.median() == 3
    assert buf.mad() > 0
