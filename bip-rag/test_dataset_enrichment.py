#!/usr/bin/env python3
"""Contract tests for RAG dataset enrichment processors."""
import os
import unittest

import prepare_dataset


class DatasetEnrichmentTests(unittest.TestCase):
    def test_extract_contact_from_submission_text(self):
        text = (
            "Osobiście przez wnioskodawcę:\n"
            "Wydział Spraw Mieszkaniowych\n"
            "ul. Peowiaków 13, pokój nr 19A (I piętro)\n"
            "20-007 Lublin\n"
            "tel. 81 466 3331\n"
            "Godziny przyjęć interesantów:\n"
            "poniedziałek, wtorek, środa, czwartek, piątek od 07:30 do 15:30."
        )

        contact = prepare_dataset.extract_contact_from_text(
            text,
            department="Wydział Spraw Mieszkaniowych",
        )

        self.assertEqual(contact["department"], "Wydział Spraw Mieszkaniowych")
        self.assertEqual(contact["address"], "ul. Peowiaków 13, 20-007 Lublin")
        self.assertEqual(contact["room"], "pokój nr 19A (I piętro)")
        self.assertEqual(contact["phone"], "81 466 3331")
        self.assertIn("07:30 do 15:30", contact["hours"])

    def test_enrichment_processors_emit_typed_documents(self):
        processors = [
            ("department_contact", prepare_dataset.process_department_contacts),
            ("faq", prepare_dataset.process_faq),
            ("fee_table", prepare_dataset.process_fee_tables),
            ("online_service", prepare_dataset.process_online_services),
            ("practical_info", prepare_dataset.process_practical_info),
            ("office_calendar", prepare_dataset.process_office_calendar),
        ]

        for expected_type, processor in processors:
            with self.subTest(expected_type=expected_type):
                docs = processor()
                self.assertGreater(len(docs), 0)
                self.assertTrue(
                    all(d["metadata"]["type"] == expected_type for d in docs),
                    f"All docs from {processor.__name__} must have type={expected_type}",
                )
                self.assertTrue(all(d["content"].strip() for d in docs))

    def test_department_contact_json_is_generated(self):
        docs = prepare_dataset.process_department_contacts()
        generated_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "data",
            "departments_contact.json",
        )

        self.assertTrue(os.path.exists(generated_path))
        self.assertGreaterEqual(len(docs), 10)
        self.assertTrue(any("Wydział Komunikacji" in d["content"] for d in docs))


if __name__ == "__main__":
    unittest.main()
