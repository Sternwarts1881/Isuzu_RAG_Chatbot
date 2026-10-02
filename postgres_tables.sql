create table work_orders
(
    work_order_id integer      not null
        constraint work_orders_id
            primary key,
    vin           varchar(17)  not null,
    description   varchar(500) not null
);

comment on column work_orders.work_order_id is 'id of a work order';

comment on constraint work_orders_id on work_orders is 'id of a work order';

comment on column work_orders.vin is 'Vehicle Identification Number';

comment on column work_orders.description is 'A detailed description of maintenance / work that needs to be done on the vehicle';
create table technical_staff
(
    UID                 integer     not null
        constraint technical_staff_uid_pk
            primary key,
    Name                varchar(50) not null,
    Surname             varchar(30) not null,
    Department          varchar(80) not null,
    Phone_number        varchar(20),
    Email               varchar(40),
    Currently_available boolean     not null
);

create table chat_sessions
(
    session_id          uuid                     default gen_random_uuid() not null
        primary key,
    technical_staff_uid integer
        references technical_staff
            on update cascade on delete cascade,
    runtime_user_id     varchar(255)                                       not null,
    created_at          timestamp with time zone default CURRENT_TIMESTAMP,
    status              varchar(20)              default 'active'::character varying
)

create table chat_messages
(
    message_id   bigserial
        primary key,
    session_id   uuid
        references chat_sessions
            on update cascade on delete cascade,
    sender_role  varchar(20) not null,
    message_text text        not null,
    created_at   timestamp with time zone default CURRENT_TIMESTAMP
)

create table error_codes
(
    error_code        varchar(10) not null,
    car_model         varchar(50) not null,
    error_explanation text        not null
)