/* Contains the pools */
CREATE TABLE polls (
  uid       TEXT NOT NULL UNIQUE,                            -- Unique identifier of the poll (use for URL and database link)
  title     TEXT NOT NULL,                                   -- Title of the poll
  message   TEXT NOT NULL,                                   -- Poll description provided to the users
  end_date  TIMESTAMP NOT NULL,                              -- Date of the end of the poll (vote cannot be edited or added after this date and results are computed)
  owner     TEXT NOT NULL,                                   -- Name of the creator (used to delete poll)
  PRIMARY KEY(uid)
);

/* Contains the choices offered by a poll */
CREATE TABLE choices (
  id    INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
  poll  TEXT NOT NULL,                                       -- Identifier of the parent poll
  text  TEXT NOT NULL,                                       -- Text of the poll presented to the user
  FOREIGN KEY(poll) REFERENCES polls(uid)
);

/* Contains the ballots. They are deleted once the results are computed */
CREATE TABLE ballots (
  voter  TEXT NOT NULL,                                      -- Name of the voter (used to edit votes)
  poll   TEXT NOT NULL,                                      -- Identifier of the parent poll
  choice INTEGER NOT NULL,                                   -- Identifier of the choice
  grade  INTEGER NOT NULL,                                   -- Grade of the choice (0 is To reject, 6 is Excellent)
  FOREIGN KEY(poll) REFERENCES polls(uid),
  FOREIGN KEY(choice) REFERENCES choices(id),
  PRIMARY KEY (voter, poll, choice)
);

/* Contains results of the poll after computation. Used to be able to store data anonymously after the vote is complete. */
CREATE TABLE  results (
  poll         TEXT NOT NULL,                                -- Identifier of the parent poll
  choice       INTEGER NOT NULL,                             -- Identifier of the choice
  rank         TEXT NOT NULL,                                -- Rank of the choice (1 is winner), may be a semicolon list when tie appeares
  grade        TEXT NOT NULL,                                -- Grade of the choice (eg. Excellent or Good+ or Acceptable- or ...)
  percentages  TEXT NOT NULL,                                -- Gross percentage of each grade (as a semicolon separeted list starting by Reject).
  ballots      INTEGER NOT NULL,                             -- Number of ballots cast 
  FOREIGN KEY(poll) REFERENCES polls(uid),
  FOREIGN KEY(choice) REFERENCES choices(id),
  PRIMARY KEY (poll, choice)
);

