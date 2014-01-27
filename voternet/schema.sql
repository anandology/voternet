
CREATE TYPE place_type AS ENUM (
    'STATE', 'PC', 'AC', 'WARD', 'PS', 'PB');

create table place (
    id serial primary key,
    name text,
    type place_type,
    code text,
    parent_id integer references place,
    state_id integer references place,
    pc_id integer references place,
    ac_id integer references place,
    ward_id integer references place,
    ps_id integer references place
);

create unique index place_code_idx on place(code, parent_id);

create table people (
    id serial primary key,
    name text,
    email text,
    phone text unique,
    place_id integer references place
);