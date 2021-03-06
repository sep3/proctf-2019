#!/usr/bin/env python3
import json
import logging
import string
import pprint

import checklib
import checklib.http
import checklib.random
import program_generator


class DroneRacingChecker(checklib.http.HttpChecker):
    port = 80

    def info(self):
        print('vulns: 1')
        self.exit(checklib.StatusCode.OK)

    def check(self, address):
        self._check_main_page()

    def put(self, address, flag_id, flag, vuln):
        name = checklib.random.from_collection("firstname") + " " + checklib.random.from_collection("lastname")
        login = checklib.random.string(string.ascii_lowercase, 10)
        password = checklib.random.string(string.ascii_lowercase, 10)
        self._register_user(name, login, password)
        self._login(login, password)

        level_title = checklib.random.english_word().capitalize() + " " + checklib.random.english_word()
        map = checklib.random.from_collection("map")
        level_id = self._upload_level(level_title, map)

        program_title = checklib.random.english_word().capitalize() + " " + checklib.random.english_word()
        source_code, params = self._generate_program_for_map(map, flag)
        program_id = self._upload_program(program_title, source_code, level_id)

        # Print flag_id for calling get() after some time
        print(json.dumps({
            "login": login,
            "password": password,
            "level_id": level_id,
            "program_id": program_id,
            "params": params,
        }))

    def get(self, address, flag_id, flag, vuln):
        data = json.loads(flag_id)
        login = data["login"]
        password = data["password"]
        level_id = data["level_id"]
        program_id = data["program_id"]
        params = data["params"]

        self._login(login, password)

        run, output = self._run_program(program_id, params)
        logging.info("Program finished at %d milliseconds" % (run["finishTime"] - run["startTime"]))
        self.mumble_if_false(run["success"], "Program should successfully pass the maze")

        logging.info('Flag is "%s", program\'s output is "%s"' % (flag, output.strip()))
        self.corrupt_if_false(output.strip() == flag, "Program didn't write a flag to the output")


    # INTERNAL METHODS:

    @staticmethod
    def _generate_company_name():
        return checklib.random.from_collection('company') + ' ' + str(checklib.random.integer(range(1000000)))

    @staticmethod
    def _generate_program_for_map(map, flag=None):
        return program_generator.generate_program(program_generator.generate_moves_sequence(map), flag)

    def _check_main_page(self):
        response = self.try_http_get(self.main_url)
        self.check_page_content(response, ['Drone racing'])

    def _register_user(self, name, login, password):
        logging.info('Try to register user "%s" with login "%s" and password "%s"' % (name, login, password))
        r = self._parse_json_response(self.try_http_post("/api/users", json={
            "name": name,
            "login": login,
            "password": password,
        }))

        user_id = int(r['user']['id'])
        logging.info('Success. User id is %d' % user_id)
        return user_id

    def _login(self, login, password):
        logging.info('Try to login user with login "%s" ans password "%s"' % (login, password))
        r = self.try_http_post("/api/users/login", json={
            "login": login,
            "password": password
        })

        logging.info('Cookies are %s' % r.cookies)
        self.mumble_if_false('session' in r.cookies, 'Can\'t authenticate as existing user')

        self._parse_json_response(r)

    def _upload_level(self, title, map):
        logging.info('Try to upload a level with map "%s"' % map)
        r = self._parse_json_response(self.try_http_post("/api/levels", json={
            "title": title,
            "map": map,
        }))

        self.mumble_if_false("level" in r and "id" in r["level"], "Can't find ['level']['id'] key in response for /api/runs")
        level_id = int(r['level']['id'])
        logging.info('Success. Level id is %d' % level_id)

        logging.info('Check that level exists (/api/levels/:id)')
        r = self._parse_json_response(self.try_http_get("/api/levels/" + str(level_id)))
        level = r['level']
        self.mumble_if_false(
            level['id'] == level_id,
            "Can't find just created level in a list at /api/levels/:id"
        )

        return level_id

    def _upload_program(self, title, source_code, level_id):
        logging.info('Try to upload a program for level %d with title "%s" and source code "\n%s\n"' % (level_id, title, source_code))
        r = self._parse_json_response(self.try_http_post("/api/programs", json={
            "title": title,
            "sourceCode": source_code,
            "levelId": level_id,
        }))

        self.mumble_if_false("programId" in r, "Can't find 'programId' key in response for /api/programs")
        program_id = int(r['programId'])

        logging.info('Success. Program id is %d' % program_id)
        return program_id

    def _run_program(self, program_id, params):
        logging.info('Try to run a program %d with params %s' % (program_id, params))
        r = self._parse_json_response(self.try_http_post("/api/runs", json={
            "programId": program_id,
            "params": params,
        }))

        self.mumble_if_false("run" in r, "Can't find 'run' key in response for /api/runs")
        self.mumble_if_false("error" in r, "Can't find 'error' key in response for /api/runs")
        self.mumble_if_false("errorMessage" in r, "Can't find 'errorMessage' key in response for /api/runs")

        run = r["run"]
        error = r["error"]
        error_message = r["errorMessage"]
        if error:
            logging.info('Received error while running a correct program. Error message: "%s"' % error_message)
            self.exit(checklib.StatusCode.MUMBLE, "Received error while running a correct program")

        return run, r["output"]

    def _parse_json_response(self, r):
        content_type = r.headers['Content-type']
        self.mumble_if_false(
            r.headers['Content-Type'].startswith('application/json'),
            'Invalid content type at %s: "%s", expected "application/json"' % (r.url, content_type)
        )

        try:
            json = r.json()
        except Exception:
            self.exit(checklib.StatusCode.MUMBLE, "Invalid json in response")
            return

        logging.debug('Parsing JSON response: %s' % pprint.pformat(json))
        self.mumble_if_false(
            json['status'] == 'ok',
            'Bad response from %s: status = %s' % (r.url, json['status'])
        )

        return json.get('response', {})


if __name__ == '__main__':
    DroneRacingChecker().run()
