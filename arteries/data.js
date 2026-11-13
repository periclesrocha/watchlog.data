/*
 * Arterial blood supply of the head and neck.
 *
 * Hierarchy follows the reference flowchart; terms and "Supplies" notes come from the
 * "Arterial Blood Supply" slide. Children are listed in slide order (the numbered
 * order), which is what "Branches must be in the same order as the slides" checks.
 *
 * Each node: { label, supplies?, note?, children? }
 */
window.ARTERY_TREE = {
  label: 'Aorta (Arch of Aorta)',
  note: 'Gives off three branches toward the head and neck.',
  children: [
    {
      label: 'Brachiocephalic Artery (Right Side)',
      children: [
        { label: 'Right Subclavian Artery', supplies: 'Neck, shoulders, upper limbs, adjacent structures' },
        { label: 'Right Common Carotid Artery', note: 'Same branching pattern as the left common carotid artery.' }
      ]
    },
    {
      label: 'Left Common Carotid Artery',
      note: 'Forms the carotid sinus swelling before dividing at the upper border of the thyroid cartilage.',
      children: [
        {
          label: 'Internal Carotid Artery',
          note: 'No branches in the neck; enters the skull through the carotid canal.',
          supplies: 'Brain, eye, orbit, forehead',
          children: [
            { label: 'Ophthalmic Artery', supplies: 'Eye, orbit, lacrimal gland' }
          ]
        },
        {
          label: 'External Carotid Artery (Symmetrical)',
          supplies: 'Extracranial tissues of the head and neck, including the oral cavity, through 4 branch sets',
          children: [
            {
              label: 'Anterior Branches',
              note: 'Branch set 1 of 4 of the external carotid artery.',
              children: [
                {
                  label: 'Superior Thyroid Artery',
                  supplies: 'Infrahyoid muscles, SCM muscle, larynx, thyroid gland',
                  children: [
                    { label: 'Infrahyoid' },
                    { label: 'Sternocleidomastoid' },
                    { label: 'Superior laryngeal' },
                    { label: 'Superior & inferior thyroid' }
                  ]
                },
                {
                  label: 'Lingual Artery',
                  supplies: 'Suprahyoid & mylohyoid muscles, sublingual salivary glands, floor of mouth, tongue',
                  children: [
                    { label: 'Lingual' },
                    { label: 'Deep lingual' },
                    { label: 'Sublingual' },
                    { label: 'Suprahyoid' }
                  ]
                },
                {
                  label: 'Facial Artery',
                  supplies: 'Soft palate, palatine muscles/tonsils, submandibular gland/lymph nodes, mylohyoid & digastric muscles, upper/lower lips, facial expression muscles, side of nose',
                  children: [
                    { label: 'Ascending palatine' },
                    { label: 'Submental' },
                    { label: 'Inferior labial' },
                    { label: 'Superior labial' },
                    { label: 'Angular' }
                  ]
                }
              ]
            },
            {
              label: 'Medial Branch',
              note: 'Branch set 2 of 4 of the external carotid artery.',
              children: [
                {
                  label: 'Ascending Pharyngeal Artery',
                  supplies: 'Pharyngeal walls, soft palate, meninges of brain',
                  children: [
                    { label: 'Pharyngeal' },
                    { label: 'Meningeal' }
                  ]
                }
              ]
            },
            {
              label: 'Posterior Branches',
              note: 'Branch set 3 of 4 of the external carotid artery.',
              children: [
                {
                  label: 'Occipital Artery',
                  supplies: 'Suprahyoid muscles, SCM muscle, occipital scalp & meninges',
                  children: [
                    { label: 'Muscular' },
                    { label: 'Sternocleidomastoid' },
                    { label: 'Auricular' },
                    { label: 'Meningeal' }
                  ]
                },
                {
                  label: 'Posterior Auricular Artery',
                  supplies: 'Inner ear, mastoid air cells',
                  children: [
                    { label: 'Auricular' },
                    { label: 'Stylomastoid' }
                  ]
                }
              ]
            },
            {
              label: 'Terminal Branches',
              note: 'Branch set 4 of 4 of the external carotid artery.',
              children: [
                {
                  label: 'Superficial Temporal Artery',
                  supplies: 'Parotid gland duct & nearby facial tissues, temporalis muscle, frontal & parietal scalp',
                  children: [
                    { label: 'Transverse facial' },
                    { label: 'Middle temporal' },
                    { label: 'Frontal' },
                    { label: 'Parietal' }
                  ]
                },
                {
                  label: 'Maxillary Artery',
                  children: [
                    { label: 'Middle meningeal', supplies: 'Meninges, via the foramen spinosum' },
                    {
                      label: 'Inferior alveolar',
                      supplies: 'Mandibular teeth & periodontium, floor of mouth, mental region, mylohyoid',
                      children: [
                        { label: 'Mylohyoid' },
                        { label: 'Mental' },
                        { label: 'Incisive' }
                      ]
                    },
                    { label: 'Deep temporal', supplies: 'Temporalis muscle' },
                    { label: 'Pterygoid', supplies: 'Lateral & medial pterygoid muscles' },
                    { label: 'Masseteric', supplies: 'Masseter muscle' },
                    { label: 'Buccal', supplies: 'Buccinator & buccal region' },
                    {
                      label: 'Posterior superior alveolar',
                      note: 'Gives off dental & alveolar branches.',
                      supplies: 'Posterior maxillary teeth & periodontium, maxillary sinus'
                    },
                    {
                      label: 'Infraorbital',
                      supplies: 'Orbital region, face, anterior maxillary teeth & periodontium',
                      children: [
                        { label: 'Orbital' },
                        { label: 'Anterior superior alveolar', note: 'Gives off dental & alveolar branches.' }
                      ]
                    },
                    {
                      label: 'Greater palatine',
                      note: 'Comes off the descending palatine artery.',
                      supplies: 'Hard & soft palates',
                      children: [
                        { label: 'Lesser palatine' }
                      ]
                    },
                    {
                      label: 'Sphenopalatine',
                      supplies: 'Nasal cavity & anterior hard palate',
                      children: [
                        { label: 'Nasopalatine' }
                      ]
                    }
                  ]
                }
              ]
            }
          ]
        }
      ]
    },
    { label: 'Left Subclavian Artery', supplies: 'Neck, shoulders, upper limbs, adjacent structures' }
  ]
};
