#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright (c) 2002-2018 "Neo4j,"
# Neo4j Sweden AB [http://neo4j.com]
#
# This file is part of Neo4j.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from uuid import uuid4
from unittest import SkipTest

from neo4j import CypherError
from neo4j.exceptions import CypherSyntaxError
from neo4j.pipelining import Pipeline, PullOrderException
from neo4j.types.graph import Node, Relationship, Path
from neobolt.packstream import Structure

from test.integration.tools import DirectIntegrationTestCase


class PipelineBasicsTestCase(DirectIntegrationTestCase):

    def test_can_run_simple_statement(self):
        pipeline = self.driver.pipeline(flush_every=0)
        pipeline.push("RETURN 1 AS n")
        for record in pipeline.pull():
            assert len(record) == 1
            assert record[0] == 1
            # TODO: why does pipeline result not look like a regular result?
            # assert record["n"] == 1
            # with self.assertRaises(KeyError):
            #    _ = record["x"]
            # assert record["n"] == 1
            # with self.assertRaises(KeyError):
            #    _ = record["x"]
            with self.assertRaises(TypeError):
                _ = record[object()]
            assert repr(record)
            assert len(record) == 1
        pipeline.close()

    def test_can_run_simple_statement_with_params(self):
        pipeline = self.driver.pipeline(flush_every=0)
        count = 0
        pipeline.push("RETURN {x} AS n", {"x": {"abc": ["d", "e", "f"]}})
        for record in pipeline.pull():
            assert record[0] == {"abc": ["d", "e", "f"]}
            # TODO: why does pipeline result not look like a regular result?
            # assert record["n"] == {"abc": ["d", "e", "f"]}
            assert repr(record)
            assert len(record) == 1
            count += 1
        pipeline.close()
        assert count == 1

    def test_can_run_write_statement_with_no_return(self):
        pipeline = self.driver.pipeline(flush_every=0)
        count = 0
        test_uid = str(uuid4())
        pipeline.push("CREATE (a:Person {uid:$test_uid})", dict(test_uid=test_uid))

        for _ in pipeline.pull():
            raise Exception("Should not return any results from create with no return")
        # Note you still have to consume the generator if you want to be allowed to pull from the pipeline again even
        # though it doesn't apparently return any items.

        pipeline.push("MATCH (a:Person {uid:$test_uid}) RETURN a LIMIT 1", dict(test_uid=test_uid))
        for _ in pipeline.pull():
            count += 1
        pipeline.close()
        assert count == 1

    def test_fails_on_bad_syntax(self):
        pipeline = self.driver.pipeline(flush_every=0)
        with self.assertRaises(CypherError):
            pipeline.push("X")
            next(pipeline.pull())

    def test_doesnt_fail_on_bad_syntax_somewhere(self):
        pipeline = self.driver.pipeline(flush_every=0)
        pipeline.push("RETURN 1 AS n")
        pipeline.push("X")
        assert next(pipeline.pull())[0] == 1
        with self.assertRaises(CypherError):
            next(pipeline.pull())

    def test_fails_on_missing_parameter(self):
        pipeline = self.driver.pipeline(flush_every=0)
        with self.assertRaises(CypherError):
            pipeline.push("RETURN {x}")
            next(pipeline.pull())

    def test_can_run_simple_statement_from_bytes_string(self):
        pipeline = self.driver.pipeline(flush_every=0)
        count = 0
        raise SkipTest("FIXME: why can't pipeline handle bytes string?")
        pipeline.push(b"RETURN 1 AS n")
        for record in pipeline.pull():
            assert record[0] == 1
            assert record["n"] == 1
            assert repr(record)
            assert len(record) == 1
            count += 1
        pipeline.close()
        assert count == 1

    def test_can_run_statement_that_returns_multiple_records(self):
        pipeline = self.driver.pipeline(flush_every=0)
        count = 0
        pipeline.push("unwind(range(1, 10)) AS z RETURN z")
        for record in pipeline.pull():
            assert 1 <= record[0] <= 10
            count += 1
        pipeline.close()
        assert count == 10

    def test_can_return_node(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            pipeline.push("CREATE (a:Person {name:'Alice'}) RETURN a")
            record_list = list(pipeline.pull())
            assert len(record_list) == 1
            for record in record_list:
                alice = record[0]
                print(alice)
                raise SkipTest("FIXME: why does pipeline result not look like a regular result?")
                assert isinstance(alice, Node)
                assert alice.labels == {"Person"}
                assert dict(alice) == {"name": "Alice"}

    def test_can_return_relationship(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            pipeline.push("CREATE ()-[r:KNOWS {since:1999}]->() RETURN r")
            record_list = list(pipeline.pull())
            assert len(record_list) == 1
            for record in record_list:
                rel = record[0]
                print(rel)
                raise SkipTest("FIXME: why does pipeline result not look like a regular result?")
                assert isinstance(rel, Relationship)
                assert rel.type == "KNOWS"
                assert dict(rel) == {"since": 1999}

    def test_can_return_path(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            test_uid = str(uuid4())
            pipeline.push(
                "MERGE p=(alice:Person {name:'Alice', test_uid: $test_uid})"
                "-[:KNOWS {test_uid: $test_uid}]->"
                "(:Person {name:'Bob', test_uid: $test_uid})"
                " RETURN p",
                dict(test_uid=test_uid)
            )
            record_list = list(pipeline.pull())
            assert len(record_list) == 1
            for record in record_list:
                path = record[0]
                print(path)
                raise SkipTest("FIXME: why does pipeline result not look like a regular result?")
                assert isinstance(path, Path)
                assert path.start_node["name"] == "Alice"
                assert path.end_node["name"] == "Bob"
                assert path.relationships[0].type == "KNOWS"
                assert len(path.nodes) == 2
                assert len(path.relationships) == 1

    def test_can_handle_cypher_error(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            pipeline.push("X")
            with self.assertRaises(CypherError):
                next(pipeline.pull())

    def test_should_not_allow_empty_statements(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            pipeline.push("")
            with self.assertRaises(CypherSyntaxError):
                next(pipeline.pull())


class PipelineSpecificBehavioursTestCase(DirectIntegrationTestCase):

    def test_can_queue_multiple_statements(self):
        count = 0
        with self.driver.pipeline(flush_every=0) as pipeline:
            pipeline.push("unwind(range(1, 10)) AS z RETURN z")
            pipeline.push("unwind(range(11, 20)) AS z RETURN z")
            pipeline.push("unwind(range(21, 30)) AS z RETURN z")
            for i in range(3):
                for record in pipeline.pull():
                    assert (i * 10 + 1) <= record[0] <= ((i + 1) * 10)
                    count += 1
        assert count == 30

    def test_pull_order_exception(self):
        """If you try and pull when you haven't finished iterating the previous result you get an error"""
        pipeline = self.driver.pipeline(flush_every=0)
        with self.assertRaises(PullOrderException):
            pipeline.push("unwind(range(1, 10)) AS z RETURN z")
            pipeline.push("unwind(range(11, 20)) AS z RETURN z")
            generator_one = pipeline.pull()
            generator_two = pipeline.pull()

    def test_pipeline_can_read_own_writes(self):
        """I am not sure that we _should_ guarantee this"""
        count = 0
        with self.driver.pipeline(flush_every=0) as pipeline:
            test_uid = str(uuid4())
            pipeline.push(
                "CREATE (a:Person {name:'Alice', test_uid: $test_uid})",
                dict(test_uid=test_uid)
            )
            pipeline.push(
                "MATCH (alice:Person {name:'Alice', test_uid: $test_uid}) "
                "MERGE (alice)"
                "-[:KNOWS {test_uid: $test_uid}]->"
                "(:Person {name:'Bob', test_uid: $test_uid})",
                dict(test_uid=test_uid)
            )
            pipeline.push("MATCH (n:Person {test_uid: $test_uid}) RETURN n", dict(test_uid=test_uid))
            pipeline.push(
                "MATCH"
                " p=(:Person {test_uid: $test_uid})-[:KNOWS {test_uid: $test_uid}]->(:Person {test_uid: $test_uid})"
                " RETURN p",
                dict(test_uid=test_uid)
            )

            # create Alice
            # n.b. we have to consume the result
            assert next(pipeline.pull(), True) == True

            # merge "knows Bob"
            # n.b. we have to consume the result
            assert next(pipeline.pull(), True) == True

            # get people
            for result in pipeline.pull():
                count += 1

                assert len(result) == 1
                person = result[0]
                print(person)
                assert isinstance(person, Structure)
                assert person.tag == b'N'
                print(person.fields)
                assert set(person.fields[1]) == {"Person"}

            print(count)
            assert count == 2

            # get path
            for result in pipeline.pull():
                count += 1

                assert len(result) == 1
                path = result[0]
                print(path)
                assert isinstance(path, Structure)
                assert path.tag == b'P'

                # TODO: return Path / Node / Rel instances rather than Structures
                # assert isinstance(path, Path)
                # assert path.start_node["name"] == "Alice"
                # assert path.end_node["name"] == "Bob"
                # assert path.relationships[0].type == "KNOWS"
                # assert len(path.nodes) == 2
                # assert len(path.relationships) == 1

        assert count == 3


class ResetTestCase(DirectIntegrationTestCase):

    def test_automatic_reset_after_failure(self):
        with self.driver.pipeline(flush_every=0) as pipeline:
            try:
                pipeline.push("X")
                next(pipeline.pull())
            except CypherError:
                pipeline.push("RETURN 1")
                record = next(pipeline.pull())
                assert record[0] == 1
            else:
                assert False, "A Cypher error should have occurred"
