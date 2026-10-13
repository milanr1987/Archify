import os
import unittest

from atlas.identity import make_id, norm_path


class IdentityTests(unittest.TestCase):
    def test_same_parts_give_same_id(self):
        self.assertEqual(make_id("skill", "a"), make_id("skill", "a"))

    def test_id_is_full_sha256_hex(self):
        value = make_id("skill", "a")
        self.assertEqual(len(value), 64)
        int(value, 16)

    def test_parts_cannot_collide_through_delimiter(self):
        self.assertNotEqual(make_id("mcp", "a|b", "c"), make_id("mcp", "a", "b|c"))

    def test_kind_and_profile_change_id(self):
        self.assertNotEqual(make_id("skill", "x"), make_id("document", "x"))
        self.assertNotEqual(make_id("plugin", "max", "p"), make_id("plugin", "pro", "p"))

    @unittest.skipUnless(os.name == "nt", "normalizacija velikih slova vrijedi na Windowsu")
    def test_windows_case_and_separators_normalized(self):
        self.assertEqual(
            norm_path("C:/Users/Milan/Some Dir/x"),
            norm_path("c:\\users\\milan\\some dir\\X"),
        )

    def test_missing_path_becomes_absolute(self):
        self.assertTrue(os.path.isabs(norm_path("ne-postoji-ovaj-folder-xyz")))


if __name__ == "__main__":
    unittest.main()
