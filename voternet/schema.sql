
CREATE TYPE place_type AS ENUM (
    'STATE', 'PC', 'AC', 'WARD', 'PS', 'PB');

create table places (
    id serial primary key,
    name text,
    type place_type,
    code text,
    info text,

    parent_id integer references places,
    state_id integer references places,
    pc_id integer references places,
    ac_id integer references places,
    ward_id integer references places,
    ps_id integer references places
);

create unique index places_code_idx on places(code, parent_id);
create index places_parent_id_idx on places(parent_id);
create index places_state_id_idx on places(state_id);
create index places_pc_id_idx on places(pc_id);
create index places_ac_id_idx on places(ac_id);
create index places_ward_id_idx on places(ward_id);
create index places_ps_id_idx on places(ps_id);

CREATE TYPE role_type AS ENUM (
    'coordinator', 'volunteer', 'admin', 'user');

create table people (
    id serial primary key,
    name text,
    email text,
    phone text,
    voterid text,
    role role_type default 'volunteer',
    active boolean default 't',
    added timestamp default(current_timestamp at time zone 'utc'),
    place_id integer references places
);

create index people_place_id_idx on people(place_id);

create table coverage (
    id serial primary key,
    place_id integer references places,
    date date,
    count integer,
    data text,
    editor_id integer references people
);

create index coverage_place_id_idx on coverage(place_id);
create index coverage_date_idx on coverage(date);
