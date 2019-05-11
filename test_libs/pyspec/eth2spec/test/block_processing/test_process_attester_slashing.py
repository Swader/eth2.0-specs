import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    get_beacon_proposer_index,
    process_attester_slashing,
)
from eth2spec.test.context import spec_state_test, expect_assertion_error
from eth2spec.test.helpers import (
    get_balance,
    get_valid_attester_slashing,
    next_epoch,
    apply_empty_block,
    make_indexed_attestation_signature
)


def run_attester_slashing_processing(state, attester_slashing, valid=True):
    """
    Run ``process_attester_slashing``, yielding:
      - pre-state ('pre')
      - attester_slashing ('attester_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    yield 'pre', state
    yield 'attester_slashing', attester_slashing

    if not valid:
        expect_assertion_error(lambda: process_attester_slashing(state, attester_slashing))
        yield 'post', None
        return

    slashed_index = attester_slashing.attestation_1.custody_bit_0_indices[0]
    pre_slashed_balance = get_balance(state, slashed_index)

    proposer_index = get_beacon_proposer_index(state)
    pre_proposer_balance = get_balance(state, proposer_index)

    # Process slashing
    process_attester_slashing(state, attester_slashing)

    slashed_validator = state.validator_registry[slashed_index]

    # Check slashing
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    # lost whistleblower reward
    assert (
            get_balance(state, slashed_index) <
            pre_slashed_balance
    )

    # gained whistleblower reward
    assert (
            get_balance(state, proposer_index) >
            pre_proposer_balance
    )

    yield 'post', state


@spec_state_test
def test_success_double(state):
    attester_slashing = get_valid_attester_slashing(state)

    yield from run_attester_slashing_processing(state, attester_slashing)


@spec_state_test
def test_success_surround(state):
    next_epoch(state)
    apply_empty_block(state)

    state.current_justified_epoch += 1
    attester_slashing = get_valid_attester_slashing(state)

    # set attestion1 to surround attestation 2
    attester_slashing.attestation_1.data.source_epoch = attester_slashing.attestation_2.data.source_epoch - 1
    attester_slashing.attestation_1.data.target_epoch = attester_slashing.attestation_2.data.target_epoch + 1

    # correct the signature of attestation 1
    make_indexed_attestation_signature(state, attester_slashing.attestation_1)

    yield from run_attester_slashing_processing(state, attester_slashing)


@spec_state_test
def test_same_data(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.data = attester_slashing.attestation_2.data

    yield from run_attester_slashing_processing(state, attester_slashing, False)


@spec_state_test
def test_no_double_or_surround(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.data.target_epoch += 1

    yield from run_attester_slashing_processing(state, attester_slashing, False)


@spec_state_test
def test_participants_already_slashed(state):
    attester_slashing = get_valid_attester_slashing(state)

    # set all indices to slashed
    attestation_1 = attester_slashing.attestation_1
    validator_indices = attestation_1.custody_bit_0_indices + attestation_1.custody_bit_1_indices
    for index in validator_indices:
        state.validator_registry[index].slashed = True

    yield from run_attester_slashing_processing(state, attester_slashing, False)


@spec_state_test
def test_custody_bit_0_and_1(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.custody_bit_1_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
    )

    yield from run_attester_slashing_processing(state, attester_slashing, False)