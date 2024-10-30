def pad(list, new_size, padding=b'0'):
    assert new_size >= len(list)
    return list + [padding] * (new_size - len(list))
