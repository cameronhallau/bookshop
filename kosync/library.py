import os
import uuid
import hashlib
import datetime
from ebooklib import epub

class Book:
    def __init__(self, path):
        self.path = path
        self.filename = os.path.basename(path)
        self.size = os.path.getsize(path)
        self.id = self._generate_id()
        self.title = "Untitled"
        self.author = "Unknown"
        self.description = ""
        self.format = "EPUB"
        
        self._load_metadata()

    def _generate_id(self):
        # Generate a deterministic ID based on the filename
        # This ensures the ID stays the same across restarts
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, self.filename))

    def _load_metadata(self):
        try:
            book = epub.read_epub(self.path)
            
            # Get title
            titles = book.get_metadata('DC', 'title')
            if titles:
                self.title = titles[0][0]
                
            # Get author
            creators = book.get_metadata('DC', 'creator')
            if creators:
                self.author = creators[0][0]
                
            # Get description
            descriptions = book.get_metadata('DC', 'description')
            if descriptions:
                self.description = descriptions[0][0]
                
        except Exception as e:
            print(f"Error reading metadata for {self.path}: {e}")

    def to_sync_event(self, host_url):
        # Construct the download URL
        download_url = f"{host_url}/download/{self.filename}"
        
        # Split author name for proper formatting
        author_parts = self.author.split(',', 1)
        if len(author_parts) == 2:
            last_name = author_parts[0].strip()
            first_name = author_parts[1].strip()
        else:
            first_name = self.author
            last_name = ""
        
        return {
            "ChangedMetadata": {
                "Authors": [{"Name": self.author}],
                "Title": self.title
            },
            "ChangeType": "NewEntitlement",
            "DateCreated": datetime.datetime.utcnow().isoformat() + "Z",
            "EntitlementId": self.id,
            "IsDeleted": False,
            "Item": {
                "ContributorRoles": [
                    {
                        "Name": self.author,
                        "Role": "Author"
                    }
                ],
                "Contributors": [first_name + " " + last_name],
                "CoverImageId": self.id,
                "Description": self.description,
                "DownloadUrls": [
                    {
                        "DRMType": "NONE",
                        "Format": "EPUB",
                        "Platform": "Generic",
                        "Size": self.size,
                        "Url": download_url
                    }
                ],
                "EntitlementId": self.id,
                "ExternalIds": [],
                "Genre": "00000000-0000-0000-0000-000000000000",
                "Id": self.id,
                "IsSocialEnabled": False,
                "Language": "en",
                "PhoneticPronunciations": {},
                "PublicationDate": datetime.datetime.utcnow().isoformat() + "Z",
                "Publisher": {"Imprint": "", "Name": "Unknown"},
                "RevisionId": self.id,
                "Title": self.title,
                "WorkId": self.id
            }
        }

class Library:
    def __init__(self, library_path):
        self.library_path = library_path
        self.books = []

    def scan(self):
        self.books = []
        if not os.path.exists(self.library_path):
            print(f"Library path does not exist: {self.library_path}")
            return

        for root, dirs, files in os.walk(self.library_path):
            for file in files:
                if file.lower().endswith('.epub'):
                    full_path = os.path.join(root, file)
                    self.books.append(Book(full_path))
        
        print(f"Scanned {len(self.books)} books.")

    def get_sync_events(self, host_url):
        return [book.to_sync_event(host_url) for book in self.books]

    def get_book_path(self, filename):
        for book in self.books:
            if book.filename == filename:
                return book.path
        return None
