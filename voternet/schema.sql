
CREATE TYPE place_type AS ENUM (
    'STATE', 'PC', 'AC', 'WARD', 'PS', 'PB');

create table place (
    id serial primary key,
    name text unique,
    type place_type,
    code text unique,
    parent_id integer references place
);

create table people (
    id serial primary key,
    name text,
    email text,
    phone text unique,
    place_id integer references place
);