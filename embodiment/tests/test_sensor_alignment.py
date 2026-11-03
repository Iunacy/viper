from copy import deepcopy
import unittest

from embodiment.contract import ADAPTERS
from embodiment.recording import validate_sensor_sample


class PhysicalSensorAlignment(unittest.TestCase):
    def test_pose_gripper_and_camera_align_for_both_native_embodiments(self):
        for robot, adapter in ADAPTERS.items():
            joints = [0.]*adapter.arm_dof+list(adapter.fingers(.5))
            row = {'timestamp': .1, 'frame': 'camera/000003.png', 'ee_position': [.17, 0., .085], 'joint_position': joints}
            physical = {'timestamp': .1, 'camera_frame': row['frame'],
                        'ee_pose': [*row['ee_position'], 1., 0., 0., 0.], 'gripper_open': .5}
            validate_sensor_sample(row, physical, robot)
            for field, value in (('timestamp', .2), ('camera_frame', 'camera/000002.png'),
                                 ('ee_pose', [.17, 0., .085, 2., 0., 0., 0.]),
                                 ('ee_pose', [.18, 0., .085, 1., 0., 0., 0.]),
                                 ('gripper_open', float('nan')), ('gripper_open', .7)):
                broken = deepcopy(physical)
                broken[field] = value
                with self.subTest(robot=robot, field=field), self.assertRaises(ValueError):
                    validate_sensor_sample(row, broken, robot)
