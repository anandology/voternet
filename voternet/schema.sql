
CREATE TYPE place_type AS ENUM (
    'STATE', 'REGION', 'PC', 'AC', 'WARD', 'PX', 'PB');

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
    px_id integer references places
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
    'coordinator', 'volunteer', 'pb_agent', 'px_agent', 'admin', 'user');

create table people (
    id serial primary key,
    name text,
    email text,
    phone text,
    voterid text,
    role role_type default 'volunteer',
    active boolean default 't',
    added timestamp default(current_timestamp at time zone 'utc'),
    place_id integer references places,
    notes text
);

create index people_place_id_idx on people(place_id);
create index people_email_idx on people(email);

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

create table unsubscribe (
    id serial primary key,
    email text,
    tstamp timestamp default (current_timestamp at time zone 'UTC')
);

-- signup invites for people who might be interested
create table invite (
    id serial primary key,
    name text,
    email text,
    phone text,
    place_id integer references places not null,
    person_id integer references people default null, -- added after signup is complete
    tstamp timestamp default (current_timestamp at time zone 'UTC'),
    batch text 
);

create index invite_batch_idx on invite(batch);
create index invite_email_idx on invite(email);
create index invite_person_id_idx on invite(person_id);

create table voterid_info (
    id serial primary key,
    voterid       text unique,
    pb_id         integer references places,
    name          text,
    rel_name      text,   
    address       text,
    age           integer,
    gender        text,
    part_no       integer,
    part          text
);

create table voter (
    id serial primary key,
    voterid     text,
    ac          integer,
    part        integer,
    srno        integer,
    name          text,
    rel_name      text,   
    gender_age     text,
    address     text
);

create index voter_voterid_idx on voter(voterid);

