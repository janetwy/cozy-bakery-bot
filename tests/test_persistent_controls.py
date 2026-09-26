import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot
import database


class PersistentControlsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(database, 'DATABASE_PATH', str(Path(self.temp.name) / 'test.db'))
        self.db_patch.start()
        database.initialize_database()
        self.session_id = database.create_session(100, 200, 'Cookies', '[]')
        database.create_version(self.session_id, 'First caption', 'response1', 'original')
        database.create_version(self.session_id, 'Second caption', 'response2', 'shorter')

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    async def test_restores_saved_view_on_restart(self):
        database.save_caption_display(self.session_id, 300, 1)
        with patch.object(bot.bot, 'add_view') as register:
            await bot.bot.setup_hook()
        view = register.call_args.args[0]
        self.assertTrue(view.is_persistent())
        self.assertEqual(view.displayed_version, 1)
        self.assertEqual(register.call_args.kwargs['message_id'], 300)
        ids = [child.custom_id for child in view.children]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn('caption:delete', ids)

    async def test_legacy_message_uses_displayed_not_latest_version(self):
        message = SimpleNamespace(id=300, content=bot.caption_message('First caption', 1, 2), edit=AsyncMock())
        result = await bot.restore_caption_message(message, database.get_session(self.session_id))
        self.assertTrue(result)
        session = database.get_session(self.session_id)
        self.assertEqual((session.caption_message_id, session.displayed_version), (300, 1))
        self.assertTrue(message.edit.call_args.kwargs['view'].is_persistent())

    async def test_navigation_saves_displayed_version(self):
        interaction = SimpleNamespace(message=SimpleNamespace(id=300, edit=AsyncMock()))
        await bot.CaptionControls(self.session_id, 1).refresh_message(interaction, 2)
        self.assertEqual(database.get_session(self.session_id).displayed_version, 2)


    async def test_migration_preserves_legacy_data_and_is_repeatable(self):
        with database.get_connection() as conn:
            conn.execute('ALTER TABLE caption_sessions DROP COLUMN caption_message_id')
            conn.execute('ALTER TABLE caption_sessions DROP COLUMN displayed_version')
        database.initialize_database()
        database.initialize_database()
        session = database.get_session(self.session_id)
        self.assertIsNone(session.caption_message_id)
        self.assertEqual(session.displayed_version, 1)
        self.assertEqual(database.get_version_count(self.session_id), 2)


if __name__ == '__main__':
    unittest.main()
