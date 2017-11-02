CREATE DATABASE IF NOT EXISTS MeleeData;
USE MeleeData

CREATE TABLE players(
    tag              VARCHAR(50) PRIMARY KEY,
    sponsor          VARCHAR(50),
    smashgg_id       INT UNSIGNED,
    rating           DOUBLE NOT NULL,
    rating_deviation DOUBLE NOT NULL,
    volatility       DOUBLE NOT NULL
    /*
    -- tournaments attended:
        SELECT id FROM tournaments t
            JOIN sets s ON t.id = s.tournament_id
            WHERE s.winner_id={player_id} OR s.loser_id={player_id};
    -- data against an opponent:
        SELECT COUNT(*) FROM sets
            WHERE winner_id={player_id} AND loser_id={opponent_id} OR winner_id={opponent_id} AND loser_id={player_id};
    -- all sets in chronological order:
        SELECT * FROM sets s
            JOIN tournaments t ON t.id = s.tournament_id
            WHERE s.winner_id={player_id} OR s.loser_id={player_id}
            ORDER BY t.date, t.id, s.is_losers, s.sets_remaining;
    --
    */
);

CREATE TABLE users(
    id          INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    username    VARCHAR(50)  NOT NULL,
    password    BINARY(64)   NOT NULL,
    tag         VARCHAR(50),
    first_name  VARCHAR(50),
    last_name   VARCHAR(50),
    facebook_id VARCHAR(50),
    FOREIGN KEY (tag)
        REFERENCES players(tag)
        ON DELETE SET NULL
    -- add other profile information
);

CREATE TABLE tournaments(
    id       VARCHAR(100) PRIMARY KEY,
    host     VARCHAR(16)  NOT NULL,
    name     VARCHAR(100) NOT NULL,
    series   VARCHAR(100),
    location VARCHAR(100) NOT NULL,
    date     TIMESTAMP    NOT NULL
    /*
    -- entrants can be found with (for example):
        SELECT (COUNT(winner_id) + COUNT(loser_id)) AS entrants
            FROM sets
            WHERE tournament_id={tournament_id} AND is_losers = FALSE AND sets_remaining=MAX(sets_remaining);
    */
);

-- bracket can be built using losers_bracket and sets_remaining, and displayed by matching match participants to prior match winner_ids
CREATE TABLE sets(
    id             INT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
    tournament_id  VARCHAR(100) NOT NULL,
    winner_tag     VARCHAR(50)  NOT NULL,
    winner_rating  DOUBLE       NOT NULL,
    loser_tag      VARCHAR(50)  NOT NULL,
    loser_rating   DOUBLE       NOT NULL,
    best_of        SMALLINT     UNSIGNED NOT NULL,
    loser_wins     SMALLINT     UNSIGNED NOT NULL,
    round_number   SMALLINT     UNSIGNED NOT NULL,
    is_losers      BOOLEAN      NOT NULL,
    title          VARCHAR(10)  NOT NULL,
    FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_tag)    REFERENCES players(tag),
    FOREIGN KEY (loser_tag)     REFERENCES players(tag)
);
