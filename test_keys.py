def _looks_like_real_key(key):
    return (
        isinstance(key, str)
        and key.startswith("gsk_")
        and len(key) >= 40
    )

# Valid key
assert _looks_like_real_key("gsk_" + "a" * 36) == True
print("PASS: real key accepted")

# Placeholder
assert _looks_like_real_key("your_key_here") == False
print("PASS: placeholder rejected")

# Empty string
assert _looks_like_real_key("") == False
print("PASS: empty string rejected")

# None
assert _looks_like_real_key(None) == False
print("PASS: None rejected")

# Short key (too short to be real)
assert _looks_like_real_key("gsk_short") == False
print("PASS: short key rejected")

print("ALL KEY VALIDATION TESTS PASSED")
