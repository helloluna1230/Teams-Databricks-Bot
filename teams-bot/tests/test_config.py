import unittest

from config import DefaultConfig, load_agent_configuration


PREFIX = "CONNECTIONS__SERVICE_CONNECTION__SETTINGS__"


class ConfigTests(unittest.TestCase):
    def test_native_managed_identity_settings(self):
        environment = {
            PREFIX + "CLIENTID": "bot-client-id",
            PREFIX + "AUTHTYPE": "UserManagedIdentity",
            "DATABRICKS_AUTH_TYPE": "oauth-m2m",
            "DATABRICKS_CLIENT_ID": "databricks-client-id",
        }
        settings = load_agent_configuration(environment)["CONNECTIONS"][
            "SERVICE_CONNECTION"
        ]["SETTINGS"]
        self.assertEqual(settings["CLIENTID"], "bot-client-id")
        self.assertEqual(settings["AUTHTYPE"], "UserManagedIdentity")
        config = DefaultConfig(environment)
        self.assertEqual(config.DATABRICKS_CLIENT_ID, "databricks-client-id")
        self.assertEqual(config.DATABRICKS_AZURE_CLIENT_ID, "bot-client-id")
        self.assertEqual(config.PORT, 8000)

    def test_legacy_settings_do_not_silently_enable_anonymous_access(self):
        with self.assertRaisesRegex(ValueError, "CLIENTID is required"):
            load_agent_configuration(
                {"MicrosoftAppId": "old-id", "MicrosoftAppType": "UserAssignedMSI"}
            )

    def test_auth_type_is_required(self):
        with self.assertRaisesRegex(ValueError, "AUTHTYPE is required"):
            load_agent_configuration({PREFIX + "CLIENTID": "bot-client-id"})

    def test_anonymous_access_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Anonymous access"):
            load_agent_configuration(
                {
                    PREFIX + "CLIENTID": "bot-client-id",
                    PREFIX + "AUTHTYPE": "UserManagedIdentity",
                    PREFIX + "ANONYMOUS_ALLOWED": "True",
                }
            )

    def test_false_anonymous_setting_is_accepted(self):
        load_agent_configuration(
            {
                PREFIX + "CLIENTID": "bot-client-id",
                PREFIX + "AUTHTYPE": "UserManagedIdentity",
                PREFIX + "ANONYMOUS_ALLOWED": "false",
            }
        )

    def test_explicit_databricks_identity_and_port_are_preserved(self):
        config = DefaultConfig(
            {"DATABRICKS_AZURE_CLIENT_ID": "data-identity", "PORT": "8080"}
        )
        self.assertEqual(config.DATABRICKS_AZURE_CLIENT_ID, "data-identity")
        self.assertEqual(config.PORT, 8080)
