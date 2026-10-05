-- Fixture schema for the offline evals.
--
-- The golden dataset is written against THIS schema, so the eval is reproducible
-- without a production database. Production golden sets should be seeded from
-- real traffic instead - see evals/README.md.

CREATE TABLE films (
    id               INTEGER PRIMARY KEY,
    title            TEXT    NOT NULL,
    release_year     INTEGER,
    runtime_minutes  INTEGER
);

CREATE TABLE people (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    birth_year  INTEGER
);

CREATE TABLE ratings (
    film_id  INTEGER NOT NULL REFERENCES films (id),
    source   TEXT    NOT NULL,
    score    REAL    NOT NULL,
    votes    INTEGER
);

CREATE TABLE credits (
    film_id    INTEGER NOT NULL REFERENCES films (id),
    person_id  INTEGER NOT NULL REFERENCES people (id),
    role       TEXT    NOT NULL
);
