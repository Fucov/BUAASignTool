import unittest

from versioning import is_newer_version, parse_version

from iclass_client import (
    VPN_OFFSET_CORRECTION_MS,
    classify_sign_response,
    extract_iclass_login_name,
    get_network_urls,
    get_sso_login_url,
    is_status_ok,
    server_time_offset_from_date,
    status_means_no_data,
    to_webvpn_url,
    value_to_string,
)


class IClassClientTests(unittest.TestCase):
    def test_release_version_comparison(self):
        self.assertEqual(parse_version("v2.4"), (2, 4))
        self.assertEqual(parse_version("release-2.10.1"), (2, 10, 1))
        self.assertIsNone(parse_version("latest"))
        self.assertTrue(is_newer_version("v2.5.0", "2.4.0"))
        self.assertTrue(is_newer_version("v2.4.1", "2.4"))
        self.assertFalse(is_newer_version("v2.4", "2.4.0"))
        self.assertFalse(is_newer_version("v2.3.9", "2.4.0"))

    def test_network_urls_match_current_iclass_paths(self):
        direct = get_network_urls(False)
        vpn = get_network_urls(True)

        self.assertEqual(
            direct["user_login"],
            "https://iclass.buaa.edu.cn:8347/app/user/login.action",
        )
        self.assertEqual(
            direct["scan_sign"],
            "http://iclass.buaa.edu.cn:8081/app/course/stu_scan_sign.action",
        )
        self.assertEqual(
            vpn["scan_sign"],
            "https://d.buaa.edu.cn/http-8081/"
            "77726476706e69737468656265737421f9f44d9d342326526b0988e29d51367ba018"
            "/app/course/stu_scan_sign.action",
        )
        self.assertIn("/https-8346/", vpn["my_center"])
        self.assertIn("/http-8081/", vpn["sign_timestamp"])

    def test_webvpn_url_preserves_path_query_and_uses_real_port(self):
        converted = to_webvpn_url(
            "https://iclass.buaa.edu.cn:8346/?type=jumpMyCenter#section"
        )
        self.assertIn("/https-8346/", converted)
        self.assertTrue(converted.endswith("/?type=jumpMyCenter#section"))
        self.assertIn("/https/", get_sso_login_url(True))

    def test_extract_login_name_preserves_base64_plus(self):
        value = extract_iclass_login_name(
            "https://example.invalid/?loginName=abc%2Bdef%2Fghi%3D&type=jump"
        )
        self.assertEqual(value, "abc+def/ghi=")

    def test_server_time_offset_uses_http_date_and_vpn_correction(self):
        date_header = "Thu, 07 May 2026 05:00:05 GMT"
        now_ms = 1778130000000

        direct_offset = server_time_offset_from_date(date_header, now_ms, use_vpn=False)
        vpn_offset = server_time_offset_from_date(date_header, now_ms, use_vpn=True)

        self.assertEqual(direct_offset, 5000)
        self.assertEqual(vpn_offset, 5000 + VPN_OFFSET_CORRECTION_MS)

    def test_status_ok_accepts_string_and_number_zero(self):
        self.assertTrue(is_status_ok({"STATUS": "0"}))
        self.assertTrue(is_status_ok({"STATUS": 0}))
        self.assertTrue(is_status_ok({"status": "0"}))
        self.assertFalse(is_status_ok({"STATUS": "2"}))
        self.assertTrue(status_means_no_data({"STATUS": 2}))

    def test_classify_sign_response_distinguishes_success_skip_and_failure(self):
        self.assertEqual(classify_sign_response({"STATUS": "0"}).status, "success")
        self.assertEqual(
            classify_sign_response({"STATUS": "1", "ERRMSG": "该课程已签到"}).status,
            "skipped",
        )
        failed = classify_sign_response({"STATUS": "1", "ERRMSG": "未到签到时间"})
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.message, "未到签到时间")

    def test_value_to_string_matches_mixed_upstream_scalars(self):
        self.assertEqual(value_to_string({"id": 123}, "id"), "123")
        self.assertEqual(value_to_string({"flag": True}, "flag"), "true")
        self.assertEqual(value_to_string({"name": "课程"}, "name"), "课程")
        self.assertEqual(value_to_string({}, "missing"), "")


if __name__ == "__main__":
    unittest.main()
