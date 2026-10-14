"""Firestore tools for Book Concierge (PageTurner)."""

import os
from typing import Any, Dict, List, Optional
from google.cloud import firestore


def get_project_id() -> str:
    """Retrieve Google Cloud project ID from environment or raise an informative error."""
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "GOOGLE_CLOUD_PROJECT environment variable is not set. "
            "Please set GOOGLE_CLOUD_PROJECT to your Google Cloud project ID."
        )
    return project_id


def get_bucket_name() -> str:
    """Retrieve Cloud Storage bucket name from environment or raise an informative error."""
    bucket_name = os.environ.get("GCS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError(
            "GCS_BUCKET_NAME environment variable is not set. "
            "Please set GCS_BUCKET_NAME to your Google Cloud Storage bucket name."
        )
    return bucket_name


_db: Optional[firestore.Client] = None


def get_db() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client(project=get_project_id())
    return _db


def list_books(status: Optional[str] = None, genre: Optional[str] = None) -> List[Dict[str, Any]]:
    """List books from the catalog/reading list, optionally filtered by reading status or genre.

    Args:
        status: Optional status to filter by ('Want to Read', 'Currently Reading', 'Finished').
        genre: Optional genre to filter by (e.g., 'Science Fiction', 'Fantasy', 'Literary Fiction').

    Returns:
        A list of book dictionaries with details like title, author, genre, status, rating, and pages.
    """
    db = get_db()
    query = db.collection("books")
    if status:
        query = query.where("status", "==", status)
    if genre:
        query = query.where("genre", "==", genre)

    docs = query.stream()
    books = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        books.append(data)
    return books


def get_book_details(title_or_id: str) -> Dict[str, Any]:
    """Retrieve full details for a book by its title or ID.

    Args:
        title_or_id: The ID or title (exact or partial match) of the book.

    Returns:
        The book details dictionary, or a message indicating it was not found.
    """
    db = get_db()
    books_ref = db.collection("books")

    # Try direct ID lookup
    doc = books_ref.document(title_or_id.lower().replace(" ", "-")).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    # Try search across collection
    for doc_snap in books_ref.stream():
        data = doc_snap.to_dict()
        data["id"] = doc_snap.id
        if (
            title_or_id.lower() in data.get("title", "").lower()
            or title_or_id.lower() == data.get("id", "").lower()
        ):
            return data

    return {"error": f"Book '{title_or_id}' not found in the catalog."}


def add_or_update_book(
    title: str,
    author: str,
    genre: str,
    pages: int,
    status: str = "Want to Read",
    current_page: int = 0,
    rating: Optional[float] = None,
    synopsis: str = "",
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Add a new book or update an existing book in the reading list / catalog.

    Args:
        title: Title of the book.
        author: Author of the book.
        genre: Genre of the book.
        pages: Total number of pages.
        status: Reading status ('Want to Read', 'Currently Reading', or 'Finished').
        current_page: Current page progress (default 0).
        rating: Optional user rating between 1.0 and 5.0.
        synopsis: Short summary/description of the book.
        tags: Optional list of thematic tags.

    Returns:
        A confirmation dictionary with the saved book details.
    """
    db = get_db()
    doc_id = title.lower().replace(" ", "-").replace(",", "").replace("'", "")
    doc_ref = db.collection("books").document(doc_id)

    book_data = {
        "id": doc_id,
        "title": title,
        "author": author,
        "genre": genre,
        "pages": pages,
        "status": status,
        "current_page": current_page,
        "rating": rating,
        "synopsis": synopsis,
        "tags": tags or [],
    }
    doc_ref.set(book_data, merge=True)
    return {"message": f"Successfully saved '{title}' to reading list.", "book": book_data}


def update_reading_progress(title_or_id: str, current_page: int, status: Optional[str] = None) -> Dict[str, Any]:
    """Update current page progress and optionally the reading status for a book.

    Args:
        title_or_id: The ID or title of the book to update.
        current_page: The new page number reached.
        status: Optional updated status ('Currently Reading', 'Finished', etc.).

    Returns:
        A dictionary with the updated book status.
    """
    db = get_db()
    book = get_book_details(title_or_id)
    if "error" in book:
        return book

    doc_ref = db.collection("books").document(book["id"])
    updates: Dict[str, Any] = {"current_page": current_page}
    if status:
        updates["status"] = status
    elif current_page >= book.get("pages", current_page):
        updates["status"] = "Finished"
    elif current_page > 0 and book.get("status") == "Want to Read":
        updates["status"] = "Currently Reading"

    doc_ref.update(updates)
    book.update(updates)
    return {"message": f"Updated progress for '{book['title']}' to page {current_page}.", "book": book}


def search_open_library(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search the external Open Library database for books by title, author, or keyword.

    Args:
        query: Search keywords, book title, or author name (e.g. 'Dune', 'Brandon Sanderson').
        limit: Maximum number of search results to return (default: 3).

    Returns:
        A list of matching book results containing title, author, publish year, pages, genres/subjects, and cover URL.
    """
    import httpx

    url = "https://openlibrary.org/search.json"
    params = {"q": query, "limit": limit}
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return [{"error": f"Failed to search Open Library: {str(e)}"}]

    results = []
    for doc in data.get("docs", [])[:limit]:
        cover_id = doc.get("cover_i")
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
        results.append({
            "title": doc.get("title"),
            "author": (doc.get("author_name") or ["Unknown"])[0],
            "first_publish_year": doc.get("first_publish_year"),
            "number_of_pages": doc.get("number_of_pages_median") or doc.get("number_of_pages"),
            "subjects": (doc.get("subject") or [])[:5],
            "cover_url": cover_url,
        })
    return results


def search_free_ebooks(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search for free public domain classic ebooks via the Gutendex (Project Gutenberg) API.

    Args:
        query: Search term (e.g., 'Pride and Prejudice', 'Frankenstein', 'Shakespeare', 'detective').
        limit: Maximum number of results to return (default: 3).

    Returns:
        A list of free ebooks with title, authors, download count, subjects, and direct read/download links (EPUB, HTML, text).
    """
    import httpx

    url = "https://gutendex.com/books/"
    params = {"search": query}
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        return [{"error": f"Failed to search Project Gutenberg ebooks: {str(e)}"}]

    results = []
    for book in data.get("results", [])[:limit]:
        formats = book.get("formats", {})
        read_online_url = formats.get("text/html") or formats.get("text/plain; charset=utf-8")
        epub_url = formats.get("application/epub+zip")
        cover_image = formats.get("image/jpeg")
        authors = [a.get("name", "Unknown") for a in book.get("authors", [])]

        results.append({
            "id": book.get("id"),
            "title": book.get("title"),
            "authors": authors,
            "downloads": book.get("download_count"),
            "subjects": book.get("subjects", [])[:4],
            "read_online_url": read_online_url,
            "epub_download_url": epub_url,
            "cover_image_url": cover_image,
        })
    return results


def generate_book_cover(prompt: str, tool_context: Any = None) -> Dict[str, Any]:
    """Generate custom book cover or scene illustration art using gemini-3.1-flash-lite-image.

    Args:
        prompt: Descriptive text prompt describing the book cover or scene art to generate.
        tool_context: ToolContext injected automatically by the agent runtime.

    Returns:
        A dictionary containing the public GCS URL of the generated image and status.
    """
    import uuid
    from google import genai
    from google.genai import types
    from google.cloud import storage

    try:
        bucket_name = get_bucket_name()
        project_id = get_project_id()
    except RuntimeError as e:
        return {"error": f"Configuration error: {str(e)}"}

    # Generate image using gemini-3.1-flash-lite-image in global region
    client = genai.Client(vertexai=True, project=project_id, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    mime_type = "image/jpeg"
    for candidate in response.candidates:
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break
        if image_bytes:
            break

    if not image_bytes:
        return {"error": "Failed to extract generated image bytes from model response."}

    # 1. Save artifact to ToolContext for Playground Artifacts panel
    filename = f"cover-{uuid.uuid4().hex[:8]}.jpg"
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )
            tool_context.save_artifact(filename, artifact_part)
        except Exception as e:
            print(f"Warning: could not save artifact to tool_context: {e}")

    # 2. Upload same bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
    return {
        "message": "Cover art generated and uploaded successfully.",
        "image_url": public_url,
        "artifact_filename": filename,
    }


def generate_book_trailer_video(prompt: str, tool_context: Any = None) -> Dict[str, Any]:
    """Generate a short video trailer or animated scene for a book using gemini-omni-flash-preview.

    Args:
        prompt: Descriptive text prompt describing the book teaser, trailer, or dramatic animated scene.
        tool_context: ToolContext injected automatically by the agent runtime.

    Returns:
        A dictionary containing the public GCS URL of the generated video and status.
    """
    import base64
    import uuid
    from google import genai
    from google.genai import types
    from google.cloud import storage

    try:
        bucket_name = get_bucket_name()
        project_id = get_project_id()
    except RuntimeError as e:
        return {"error": f"Configuration error: {str(e)}"}

    # Generate short video using gemini-omni-flash-preview in global region
    client = genai.Client(vertexai=True, project=project_id, location="global")
    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    output_video = getattr(interaction, "output_video", None)
    if not output_video:
        return {"error": "Failed to generate video: no output_video returned."}

    raw_data = output_video["data"] if isinstance(output_video, dict) else getattr(output_video, "data", None)
    mime_type = (
        output_video["mime_type"]
        if isinstance(output_video, dict)
        else getattr(output_video, "mime_type", None)
    ) or "video/mp4"

    if not raw_data:
        return {"error": "Failed to extract video data from interaction response."}

    video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
    filename = f"trailer-{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save artifact to ToolContext for Playground Artifacts panel
    if tool_context and hasattr(tool_context, "save_artifact"):
        try:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=video_bytes,
                    mime_type=mime_type,
                )
            )
            tool_context.save_artifact(filename, artifact_part)
        except Exception as e:
            print(f"Warning: could not save artifact to tool_context: {e}")

    # 2. Upload same bytes to public Cloud Storage bucket
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
    return {
        "message": "Book trailer video generated and uploaded successfully.",
        "video_url": public_url,
        "artifact_filename": filename,
    }




