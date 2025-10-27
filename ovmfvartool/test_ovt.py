import unittest
import io
import binascii
import tempfile

from ovmfvartool import FirmwareVolumeHeader, VariableStoreHeader, AuthenticatedVariable, resolveUUID


class OvmfVarToolTestCase(unittest.TestCase):
    def setUp(self):
        self.var_path = tempfile.NamedTemporaryFile()
        self.create_blank()

    def create_blank(self):
        with open(self.var_path.name, "wb") as fo:
            fm = io.BytesIO(b"\xff" * (528 * 1024))
            fm.write(FirmwareVolumeHeader.create().serialize())
            fm.write(VariableStoreHeader.create().serialize())

            fm.seek(0x41000)
            fm.write(
                binascii.unhexlify(
                    b"2b29589e687c7d49a0ce6500fd9f1b952caf2c64feffffffe00f000000000000"
                )
            )
            fm.seek(0)
            fo.write(fm.read())

    def read_content(self) -> dict[str, dict[str, AuthenticatedVariable]] | None:
        with open(self.var_path.name, "rb") as f:
            fvh = FirmwareVolumeHeader.deserialize(f)
            vsh = VariableStoreHeader.deserialize(f)
            _ = fvh
            _ = vsh
            variables: dict[str, dict[str, AuthenticatedVariable]] = {}

            while True:
                v = AuthenticatedVariable.deserialize(f)
                if not v:
                    break
                if v.isDeleted:
                    continue

                k = resolveUUID(v.vendorUUID)
                variables.setdefault(k, {})
                variables[k][v.name] = v

            return variables

    def write(self, add: list[AuthenticatedVariable]) -> None:
        variables = self.read_content()
        if not variables:
            variables = {}

        for var in add:
            k = resolveUUID(var.vendorUUID)
            variables.setdefault(k, {})
            variables[k][var.name] = var

        with open(self.var_path.name, "wb") as fo:
            fm = io.BytesIO(b"\xff" * (528 * 1024))
            fm.write(FirmwareVolumeHeader.create().serialize())
            fm.write(VariableStoreHeader.create().serialize())

            for _, vendor in variables.items():
                for _, v in vendor.items():
                    fm.write(v.serialize())
                    if fm.tell() % 4:
                        fm.write(b"\xff" * (4 - (fm.tell() % 4)))
                    assert (fm.tell() % 4) == 0

            fm.seek(0x41000)
            fm.write(
                binascii.unhexlify(
                    b"2b29589e687c7d49a0ce6500fd9f1b952caf2c64feffffffe00f000000000000"
                )
            )
            fm.seek(0)
            fo.write(fm.read())

    def test_append_var(self):
        foo = AuthenticatedVariable.deserializeFromDocument(
            '38e069f2-1212-4280-beaa-4fd3ba31e6f5',
            'Foo',
            {'Data': b'abc'}
        )

        self.write([foo])

        variables = self.read_content()
        self.assertEqual(variables['38e069f2-1212-4280-beaa-4fd3ba31e6f5']['Foo'], foo)
