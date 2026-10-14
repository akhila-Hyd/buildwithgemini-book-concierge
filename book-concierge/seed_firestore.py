"""Seed script for the Book Concierge Firestore database."""

import os
from google.cloud import firestore

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
if not PROJECT_ID:
    raise RuntimeError(
        "GOOGLE_CLOUD_PROJECT environment variable is not set. "
        "Please run with: GOOGLE_CLOUD_PROJECT=your-project-id python seed_firestore.py"
    )

SAMPLE_BOOKS = [
    {
        "id": "project-hail-mary",
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "genre": "Science Fiction",
        "pages": 496,
        "rating": 4.8,
        "status": "Currently Reading",
        "current_page": 210,
        "synopsis": "A lone astronaut must save the Earth from an extinction-level catastrophe with unexpected extraterrestrial help.",
        "tags": ["space", "first contact", "hard sci-fi", "humor"],
    },
    {
        "id": "tomorrow-and-tomorrow",
        "title": "Tomorrow, and Tomorrow, and Tomorrow",
        "author": "Gabrielle Zevin",
        "genre": "Literary Fiction",
        "pages": 416,
        "rating": 4.5,
        "status": "Want to Read",
        "current_page": 0,
        "synopsis": "Two childhood friends collaborate to design blockbuster video games, exploring identity, creativity, and love over three decades.",
        "tags": ["video games", "friendship", "creative partnership"],
    },
    {
        "id": "the-priory-of-the-orange-tree",
        "title": "The Priory of the Orange Tree",
        "author": "Samantha Shannon",
        "genre": "Fantasy",
        "pages": 848,
        "rating": 4.6,
        "status": "Finished",
        "current_page": 848,
        "synopsis": "An epic tale of an undivided world threatened by an ancient dragon, spanning an unwed queen, dragon riders, and ancient magic.",
        "tags": ["dragons", "high fantasy", "magic", "multiple pov"],
    },
    {
        "id": "atomic-habits",
        "title": "Atomic Habits",
        "author": "James Clear",
        "genre": "Self-Help / Psychology",
        "pages": 320,
        "rating": 4.7,
        "status": "Finished",
        "current_page": 320,
        "synopsis": "A practical framework for improving every day through tiny, compounding changes in behavior and habits.",
        "tags": ["productivity", "habits", "mindset"],
    },
    {
        "id": "klara-and-the-sun",
        "title": "Klara and the Sun",
        "author": "Kazuo Ishiguro",
        "genre": "Dystopian / Sci-Fi",
        "pages": 303,
        "rating": 4.2,
        "status": "Want to Read",
        "current_page": 0,
        "synopsis": "The story of Klara, an Artificial Friend with outstanding observational qualities, who watches the behavior of customers and passers-by.",
        "tags": ["ai", "dystopia", "philosophical", "heartfelt"],
    },
]


def seed():
    db = firestore.Client(project=PROJECT_ID)
    collection = db.collection("books")
    print(f"Seeding books collection into Firestore project: {PROJECT_ID}")
    for book in SAMPLE_BOOKS:
        doc_id = book["id"]
        collection.document(doc_id).set(book)
        print(f"Seeded: {book['title']} ({doc_id})")
    print("Seeding completed successfully!")


if __name__ == "__main__":
    seed()
