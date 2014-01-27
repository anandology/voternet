
CREATE TYPE place_type AS ENUM (
    'STATE', 'PC', 'AC', 'WARD', 'PS', 'PB');

create table places (
    id serial primary key,
    name text,
    type place_type,
    code text,
    parent_id integer references places,
    state_id integer references places,
    pc_id integer references places,
    ac_id integer references places,
    ward_id integer references places,
    ps_id integer references places
);

create unique index places_code_idx on places(code, parent_id);

create table people (
    id serial primary key,
    name text,
    email text,
    phone text,
    place_id integer references places
);