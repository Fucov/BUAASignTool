import unittest

from iclass_client import (
    VPN_OFFSET_CORRECTION_MS,
    classify_sign_response,
    get_network_urls,
    is_status_ok,
    server_time_offset_from_date,
    value_to_string,
)


class IClassClientTests(unittest.TestCase):
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
            "https://d.buaa.edu.cn/https-8347/"
            "77726476706e69737468656265737421f9f44d9d342326526b0988e29d51367ba018"
            "/app/course/stu_scan_sign.action",
        )

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
