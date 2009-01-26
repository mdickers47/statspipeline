--
-- PostgreSQL database dump
--

SET client_encoding = 'UTF8';
SET standard_conforming_strings = off;
SET check_function_bodies = false;
SET client_min_messages = warning;
SET escape_string_warning = off;

SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: log; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE log (
    id integer NOT NULL,
    event_time timestamp without time zone DEFAULT now() NOT NULL,
    class character varying(64) NOT NULL,
    instance character varying(64) NOT NULL,
    event character varying(255) NOT NULL
);


--
-- Name: log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE log_id_seq
    INCREMENT BY 1
    NO MAXVALUE
    NO MINVALUE
    CACHE 1;


--
-- Name: log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE log_id_seq OWNED BY log.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE log ALTER COLUMN id SET DEFAULT nextval('log_id_seq'::regclass);


--
-- Name: log_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY log
    ADD CONSTRAINT log_pkey PRIMARY KEY (id);


--
-- Name: public; Type: ACL; Schema: -; Owner: -
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

