# Модели SQLAlchemy для таблиц фильмов и связанных сущностей
from sqlalchemy import (
    Column,
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
from sqlalchemy.orm import relationship

from src.database import Base


class Certification(Base):
    __tablename__ = "certifications"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)


class Star(Base):
    __tablename__ = "stars"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)


class Director(Base):
    __tablename__ = "directors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="uq_movie_name_year_time"),
    )

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)

    name = Column(String(300), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    time = Column(Integer, nullable=False)  # length in minutes

    imdb = Column(Float, nullable=False)
    votes = Column(Integer, nullable=False)
    meta_score = Column(Integer, nullable=True)
    gross = Column(Numeric(12, 2), nullable=True)

    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)

    certification_id = Column(Integer, ForeignKey("certifications.id"), nullable=True)
    certification = relationship("Certification", backref="movies")


class MovieGenre(Base):
    __tablename__ = "movie_genres"

    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id"), primary_key=True)

    movie = relationship("Movie", backref="movie_genres")
    genre = relationship("Genre", backref="movie_genres")


class MovieStar(Base):
    __tablename__ = "movie_stars"

    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    star_id = Column(Integer, ForeignKey("stars.id"), primary_key=True)

    movie = relationship("Movie", backref="movie_stars")
    star = relationship("Star", backref="movie_stars")


class MovieDirector(Base):
    __tablename__ = "movie_directors"

    movie_id = Column(Integer, ForeignKey("movies.id"), primary_key=True)
    director_id = Column(Integer, ForeignKey("directors.id"), primary_key=True)

    movie = relationship("Movie", backref="movie_directors")
    director = relationship("Director", backref="movie_directors")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("comments.id"), nullable=True, index=True)

    text = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", backref="comments")
    movie = relationship("Movie", backref="comments")
    parent = relationship("Comment", remote_side=[id], backref="replies")
