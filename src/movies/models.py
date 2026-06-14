from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base

if TYPE_CHECKING:
    from src.accounts.models import User  # for type checking only


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)


class Star(Base):
    __tablename__ = "stars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)


class Director(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    time: Mapped[int] = mapped_column(Integer, nullable=False)  # length in minutes

    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross: Mapped[Numeric | None] = mapped_column(Numeric(12, 2), nullable=True)

    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Numeric] = mapped_column(Numeric(10, 2), nullable=False)

    certification_id: Mapped[int | None] = mapped_column(
        ForeignKey("certifications.id"), nullable=True
    )
    certification: Mapped[Certification | None] = relationship(
        "Certification", backref="movies"
    )


class MovieGenre(Base):
    __tablename__ = "movie_genres"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"), primary_key=True)

    movie: Mapped[Movie] = relationship("Movie", backref="movie_genres")
    genre: Mapped[Genre] = relationship("Genre", backref="movie_genres")


class MovieStar(Base):
    __tablename__ = "movie_stars"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)
    star_id: Mapped[int] = mapped_column(ForeignKey("stars.id"), primary_key=True)

    movie: Mapped[Movie] = relationship("Movie", backref="movie_stars")
    star: Mapped[Star] = relationship("Star", backref="movie_stars")


class MovieDirector(Base):
    __tablename__ = "movie_directors"

    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), primary_key=True)
    director_id: Mapped[int] = mapped_column(
        ForeignKey("directors.id"), primary_key=True
    )

    movie: Mapped[Movie] = relationship("Movie", backref="movie_directors")
    director: Mapped[Director] = relationship("Director", backref="movie_directors")


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), nullable=True, index=True
    )

    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship("User", backref="comments")
    movie: Mapped[Movie] = relationship("Movie", backref="comments")
    parent: Mapped[Comment | None] = relationship(
        "Comment", remote_side=[id], backref="replies"
    )
