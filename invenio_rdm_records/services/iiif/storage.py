"""IIIF Tiles generation storage."""

import os
import shutil
from pathlib import Path
from textwrap import wrap
from typing import Union

from flask import current_app

from invenio_rdm_records.records.api import RDMRecord
from invenio_rdm_records.services.iiif.converter import (
    ImageConverter,
    PyVIPSImageConverter,
)


class TilesStorage:
    """Base class for tile storage."""

    def __init__(self, *, converter: ImageConverter):
        """Constructor."""
        self.converter = converter

    def save(self, record: RDMRecord, filename: str):
        """Save tiles."""
        pass

    def open(self, record: RDMRecord, filename: str):
        """Open file in read mode."""
        pass

    def delete(self, record: RDMRecord, filename: str):
        """Delete tiles file."""
        pass


class LocalTilesStorage(TilesStorage):
    """Local tile storage implementation."""

    def __init__(
        self,
        *,
        output_path: Union[str, None] = None,
        converter: ImageConverter = None,
        **kwargs,
    ):
        """Constructor."""
        converter = converter or PyVIPSImageConverter()
        self.output_path = output_path and output_path
        super().__init__(converter=converter, **kwargs)

    @property
    def base_path(self):
        return self.output_path or Path(current_app.config.get("IIIF_TILES_BASE_PATH"))

    def _get_dir(self, record: RDMRecord) -> Path:
        """Get directory."""
        recid = record.pid.pid_value

        recid_parts = wrap(recid.ljust(4, "_"), 2)
        start_parts = recid_parts[:2]
        end_parts = recid_parts[2:]
        recid_path = "/".join(start_parts)
        if end_parts:
            recid_path += f"/{''.join(end_parts)}_"
        else:
            recid_path += "/_"

        path_partitions = recid_path.split("/")

        return (
            self.base_path / record.access.protection.files / Path(*path_partitions)
        ).absolute()

    def _get_file_path(self, record: RDMRecord, filename: str) -> Path:
        """Get file path."""
        # Partition record.id into 3 chunks of min. 2 characters (e.g. "12345678" -> ["12", "34", "5678"])
        return (self._get_dir(record) / (filename + ".ptif")).absolute()

    def save(self, record, filename):
        """Convert and save to ptif."""
        # TODO don't regenerate?
        outpath = self._get_file_path(record, filename)
        # if outpath.exists():
        #     return True

        self._get_dir(record).mkdir(parents=True, exist_ok=True)
        with record.files[filename].open_stream("rb") as fin:
            fout = outpath.open("w+b")
            if not self.converter.convert(fin, fout):
                current_app.logger.info(f"Image conversion failed {record.id}")
                return False
        return True

    def open(self, record, filename):
        """Open the file in read mode."""
        return self._get_file_path(record, filename).open("rb")

    def update_access(self, record):
        """Move files according to current files access of the record"""
        access = record.access.protection.files
        directory = str(self._get_dir(record))
        old_dir = str(directory).replace(
            access,
            "restricted" if access == "public" else "public",
        )
        if os.path.exists(old_dir):
            shutil.move(old_dir, directory)

    def delete(self, record, filename):
        """Delete the ptif."""
        # TODO: this filename is the ptif name, should it be the file name?
        Path(record.media_files[filename].file.uri).unlink(missing_ok=True)


tiles_storage = LocalTilesStorage()