import base64
import os

from mutagen.flac import VCFLACDict
from mutagen.id3 import ID3

from applications.task.utils import detect_language
from component import music_tag


class MusicIDS:
    def __init__(self, folder=None, file=None):
        if folder:
            folder = folder.encode('utf-8', 'replace').decode()
            self.file = music_tag.load_file(folder)
            self.path = folder
        elif file:
            folder = file.filename.encode('utf-8', 'replace').decode()
            self.file = file
            self.path = folder
        self.artwork_w = 0
        self.artwork_h = 0
        self.artwork_size = 0

    @property
    def album_name(self):
        try:
            album_name = str(self.file["album"].value or "").strip()
            if not album_name:
                return "未知专辑"
            return album_name
        except Exception:
            return "未知专辑"

    @property
    def album(self):
        try:
            album_name = str(self.file["album"].value or "").strip()
            return album_name
        except Exception:
            return ""

    @property
    def album_type(self):
        try:
            if isinstance(self.file.mfile.tags, VCFLACDict):
                tags = self.file.mfile.tags.get("RELEASETYPE", [""])
                return str(tags[0]) if tags else ""
            elif isinstance(self.file.mfile.tags, ID3):
                tag = self.file.mfile.tags.get("TXXX:MusicBrainz Album Type")
                if tag and getattr(tag, "text", None):
                    return str(tag.text[0])
            return ""
        except Exception:
            return ""

    @property
    def album_artist(self):
        try:
            val = self.file["albumartist"].value
            return str(val).strip() if val else ""
        except Exception:
            return ""

    @property
    def albumartist(self):
        return self.album_artist

    @property
    def artist_name(self):
        return self.artist

    @property
    def artist(self):
        try:
            val = self.file["artist"].value
            return str(val).strip() if val else ""
        except Exception:
            return ""

    @property
    def year(self):
        try:
            year = self.file["year"].value
            if year:
                year_list = str(year).split("-")
                if year_list and year_list[0]:
                    import re
                    m = re.search(r'\d+', year_list[0])
                    if m:
                        return int(m.group(0))
        except Exception:
            pass
        return 0

    @property
    def genre(self):
        try:
            genre = self.file["genre"].value
            if genre:
                return str(genre).strip().upper()
        except Exception:
            pass
        return "未知"

    @property
    def comment(self):
        try:
            val = self.file["comment"].value
            return str(val).strip() if val else ""
        except Exception:
            return ""

    @property
    def lyrics(self):
        try:
            val = self.file["lyrics"].value
            return str(val).strip() if val else ""
        except Exception:
            return ""

    @property
    def duration(self):
        try:
            return round(self.file['#length'].value, 2)
        except Exception:
            return 0.0

    @property
    def size(self):
        try:
            return round(os.path.getsize(self.path) / 1024 / 1024, 2)
        except Exception:
            return 0.0

    @property
    def suffix(self):
        try:
            return str(self.file['#codec'].value)
        except Exception:
            return os.path.splitext(self.path)[-1].lstrip('.').lower()

    @property
    def bit_rate(self):
        try:
            return int(self.file['#bitrate'].value / 1000)
        except Exception:
            return 0

    @property
    def track_number(self):
        try:
            val = self.file['tracknumber'].value
            if val is not None and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
        try:
            if hasattr(self.file, "mfile") and self.file.mfile and getattr(self.file.mfile, "tags", None):
                tags = self.file.mfile.tags
                if "TRCK" in tags:
                    val = str(tags["TRCK"][0]).split("/")[0].strip()
                    if val:
                        return val
                if "tracknumber" in tags:
                    val = str(tags["tracknumber"][0]).split("/")[0].strip()
                    if val:
                        return val
        except Exception:
            pass
        return "0"

    @property
    def tracknumber(self):
        return self.track_number

    @property
    def disc_number(self):
        try:
            val = self.file['discnumber'].value
            if val is not None and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
        try:
            if hasattr(self.file, "mfile") and self.file.mfile and getattr(self.file.mfile, "tags", None):
                tags = self.file.mfile.tags
                if "TPOS" in tags:
                    val = str(tags["TPOS"][0]).split("/")[0].strip()
                    if val:
                        return val
                if "discnumber" in tags:
                    val = str(tags["discnumber"][0]).split("/")[0].strip()
                    if val:
                        return val
        except Exception:
            pass
        return "0"

    @property
    def discnumber(self):
        return self.disc_number

    @property
    def title(self):
        try:
            val = self.file['title'].value
            return str(val).strip() if val else ""
        except Exception:
            return ""

    @property
    def artwork(self):
        try:
            bs64_img = ""
            artwork = self.file['artwork'].values
            if artwork:
                if isinstance(artwork[0], bytes):
                    # eval_artwork = literal_eval(artwork[0])
                    # with open("test.xmp", "wb") as f:
                    #     f.write(artwork[0])
                    bs64_img = base64.b64encode(artwork[0]).decode()

                else:
                    zip_img = artwork[0].raw_thumbnail([128, 128])
                    bs64_img = base64.b64encode(zip_img).decode()
                    self.artwork_w = artwork[0].width
                    self.artwork_h = artwork[0].height
                    self.artwork_size = round(len(artwork[0].raw) / 1024 / 1024, 2)
            return "data:image/jpeg;base64," + bs64_img
        except Exception as e:
            print(e)
            return ""

    @property
    def file_name(self):
        return os.path.basename(self.path)

    @property
    def language(self):
        try:
            if isinstance(self.file.mfile.tags, VCFLACDict):
                language = self.file.mfile.tags.get("LANGUAGE")[0]
            elif isinstance(self.file.mfile.tags, ID3):
                language = self.file.mfile.tags.get("TXXX:LANGUAGE").text[0]
            else:
                language = ""
        except Exception:
            language = ""
        if language:
            return language
        else:
            try:
                return detect_language(self.lyrics)
            except Exception:
                return ""

    def to_dict(self):
        return {
            "year": self.year,
            "comment": self.comment,
            "lyrics": self.lyrics,
            "duration": self.duration,
            "size": self.size,
            "bit_rate": self.bit_rate,
            "tracknumber": self.track_number,
            "discnumber": self.disc_number,
            "artwork": self.artwork,
            "artwork_w": self.artwork_w,
            "artwork_h": self.artwork_h,
            "artwork_size": self.artwork_size,
            "title": self.title or self.file_name.split(".")[0],
            "artist": self.artist,
            "album": self.album,
            "album_type": self.album_type,
            "genre": self.genre,
            "filename": self.file_name,
            "albumartist": self.album_artist,
            "language": self.language,
        }

    def var_dict(self):
        filename_no_ext = os.path.splitext(self.file_name)[0]
        parent_dir = ""
        if self.path:
            parent_dir = os.path.basename(os.path.dirname(os.path.normpath(self.path)))
        return {
            "title": self.title or filename_no_ext,
            "artist": self.artist,
            "albumartist": self.album_artist,
            "discnumber": self.disc_number,
            "tracknumber": self.track_number,
            "album": self.album,
            "filename": self.file_name,
            "filename_no_ext": filename_no_ext,
            "basename": filename_no_ext,
            "folder": parent_dir,
            "parent_folder": parent_dir,
            "dirname": parent_dir,
            "folder_name": parent_dir,
            "year": self.year,
            "genre": self.genre,
        }
