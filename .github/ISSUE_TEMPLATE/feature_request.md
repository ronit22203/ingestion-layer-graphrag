name: Feature Request
description: Suggest an enhancement or new feature
title: "[FEATURE] "
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for suggesting an enhancement! Please describe your feature request clearly.
  
  - type: textarea
    id: problem
    attributes:
      label: Problem Statement
      description: What problem does this solve?
      placeholder: Describe the problem or limitation...
    validations:
      required: true
  
  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: How should this be implemented?
      placeholder: Describe your proposed solution...
    validations:
      required: true
  
  - type: textarea
    id: alternatives
    attributes:
      label: Alternative Solutions
      description: Other approaches considered
      placeholder: Any alternative implementations?
  
  - type: textarea
    id: use_case
    attributes:
      label: Use Case
      description: How would this feature be used?
      placeholder: Example usage or benefit...
    validations:
      required: true
  
  - type: textarea
    id: additional
    attributes:
      label: Additional Context
      description: Any other relevant information
      placeholder: Related issues, references, etc.
