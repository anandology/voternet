
CREATE TYPE place_type AS ENUM (
    'STATE', 'REGION', 'PC', 'AC', 'WARD', 'PS', 'PB');

create table places (
    id serial primary key,
    key text unique,
    name text,
    type place_type,
    code text,
    info text,

    parent_id integer references places,
    state_id integer references places,
    region_id integer references places,
    pc_id integer references places,
    ac_id integer references places,
    ward_id integer references places,
    ps_id integer references places
);

create unique index places_code_idx on places(code, parent_id);
create index places_parent_id_idx on places(parent_id);
create index places_state_id_idx on places(state_id);
create index places_region_id_idx on places(region_id);
create index places_pc_id_idx on places(pc_id);
create index places_ac_id_idx on places(ac_id);
create index places_ward_id_idx on places(ward_id);
create index places_ps_id_idx on places(ps_id);


create table things (
    id serial primary key,
    key text unique,
    type text,
    data text
);

create index things_type_idx on things(type);

CREATE TYPE role_type AS ENUM (
    'coordinator', 'volunteer', 'pb_agent', 'admin', 'user');

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
create index people_email_idx on people(email);
create index people_reset_token_idx on people(reset_token);

create table auth (
    id serial primary key,
    email text unique,
    password text,
    reset_token text unique
);

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

create table activity (
    id serial primary key,
    type text,
    place_id integer references places,
    person_id integer references people,
    data text,
    tstamp timestamp default (current_timestamp at time zone 'UTC')
);

create index activity_type_idx on activity(type);
create index activity_place_id_idx on activity(place_id);
create index activity_person_id_idx on activity(type);
create index activity_tstamp_idx on activity(tstamp);
